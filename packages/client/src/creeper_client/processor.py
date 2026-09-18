"""Receive validated site files and run collection without blocking heartbeats."""

import base64
import os
import re
import tempfile
import threading
from pathlib import Path

import yaml
from creeper_core.daemon import Daemon
from creeper_core.logger import Logger
from creeper_core.settings import load_settings, validate_site


class Processor:
    def __init__(self, settings=None, report=None, daemon_factory=None):
        self.settings = settings or load_settings()
        self.directory = Path(self.settings["received-config-dir"])
        self.report = report or (lambda data: None)
        self.daemon_factory = daemon_factory or Daemon.from_settings
        self.logger = Logger()
        self._lock = threading.Lock()
        self._worker = None
        self._daemon = None
        self._closing = False

    def process_command(self, data):
        if data["type"] == "task":
            self.process_task(data)
        elif data["type"] == "file":
            self.process_file_command(data)
        elif data["type"] == "op":
            self.process_operation_command(data)
        else:
            raise ValueError(f"Unsupported command type: {data['type']}")

    def process_task(self, data):
        task_id = data.get("task_id")
        if not isinstance(task_id, str) or not task_id or len(task_id) > 128:
            raise ValueError("Invalid task_id")
        site = validate_site(data.get("site"))
        with self._lock:
            if self._closing or self._daemon is not None:
                raise ValueError("Worker is already busy")
            daemon = self.daemon_factory(self.settings)
            daemon.yaml_loaded_data = [site]
            self._daemon = daemon
            self._worker = threading.Thread(
                target=self._run_task, args=(task_id, daemon), name="assigned-crawl"
            )
            self._worker.start()

    def _run_task(self, task_id, daemon):
        results, errors = [], []
        try:
            results = daemon.creeper()
            errors = daemon.errors
        except Exception as error:
            errors = [{"error": str(error)}]
        message = {
            "type": "task-result",
            "task_id": task_id,
            "results": [{**row, "Date": row["Date"].isoformat()} for row in results],
            "errors": errors,
        }
        # Mark idle before reporting so the next assignment can start immediately.
        with self._lock:
            self._daemon = None
            closing = self._closing
        if not closing:
            try:
                self.report(message)
            except ValueError:
                self.report(
                    {
                        "type": "task-result",
                        "task_id": task_id,
                        "results": [],
                        "errors": [{"error": "Task results exceed the 4 MiB protocol limit; saved locally"}],
                    }
                )

    def reset_session(self):
        self.close()
        with self._lock:
            self._closing = False
            self._daemon = None
            self._worker = None

    @staticmethod
    def validate_filename(filename):
        if (
            not isinstance(filename, str)
            or len(filename) > 160
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*\.ya?ml", filename)
            or filename.split(".")[0].upper()
            in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            }
        ):
            raise ValueError("filename must be a plain .yaml/.yml filename without paths")
        return filename

    def process_file_command(self, data):
        filename = self.validate_filename(data.get("filename"))
        content = data.get("content")
        if not isinstance(content, str) or len(content) > 1_400_000:
            raise ValueError("Configuration file is missing or too large")
        decoded = base64.b64decode(content, validate=True)
        validate_site(yaml.safe_load(decoded.decode("utf-8")), filename)
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / filename
        if destination.is_symlink():
            raise ValueError("Refusing a symbolic-link destination")
        fd, temporary = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(decoded)
            os.replace(temporary, destination)
        finally:
            Path(temporary).unlink(missing_ok=True)
        self.report({"type": "status", "state": "file-saved", "filename": filename})

    def process_operation_command(self, data):
        if data.get("op") != "start":
            raise ValueError("Only the start operation is supported")
        filenames = data.get("files")
        if not isinstance(filenames, list) or not filenames:
            raise ValueError("start requires a non-empty files list")
        filenames = [self.validate_filename(name) for name in filenames]
        with self._lock:
            if self._closing or (self._worker and self._worker.is_alive()):
                self.report({"type": "status", "state": "busy"})
                return
            daemon = self.daemon_factory(self.settings, config_path=self.directory)
            daemon.detect(filenames)
            self._daemon = daemon
            self._worker = threading.Thread(target=self._run, args=(daemon,), name="node-crawl")
            self._worker.start()

    def _run(self, daemon):
        try:
            self.report({"type": "status", "state": "running"})
            results = daemon.creeper()
            self.report(
                {
                    "type": "status",
                    "state": "completed" if not daemon.errors else "partial-failure",
                    "collections": len(results),
                    "records": sum(len(row["content"]) for row in results),
                    "errors": len(daemon.errors),
                }
            )
        except Exception as error:
            self.logger.error(f"Node task failed: {error}")
            self.report({"type": "status", "state": "failed", "error": str(error)})

    def close(self):
        with self._lock:
            self._closing = True
            if self._daemon:
                self._daemon.stop()
            worker = self._worker
        if worker:
            worker.join()
