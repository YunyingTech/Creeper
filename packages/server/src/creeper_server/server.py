"""Authenticated job scheduling: one leased job per connected worker."""

import hmac
import json
import socket
import threading
import time
import uuid
from pathlib import Path

import yaml
from creeper_core.logger import Logger
from creeper_core.protocol import JsonConnection, send_encode
from creeper_core.settings import load_sites

from creeper_server.tasks import TaskStore


class Server:
    def __init__(
        self,
        PORT,
        max_connection=16,
        *,
        host="127.0.0.1",
        token="",
        config_dir=None,
        auto_start=True,
        database_path=None,
        repeat=False,
        max_attempts=3,
    ):
        if host not in ("127.0.0.1", "localhost", "::1") and not token:
            raise ValueError("A non-loopback server requires CREEPER_TOKEN or auth-token")
        self.PORT, self.max_connection, self.host, self.token = PORT, max_connection, host, token
        self.config_dir = Path(config_dir or Path.cwd() / "config")
        self.database_path = database_path or Path.cwd() / "data/server.sqlite3"
        self.auto_start, self.repeat, self.max_attempts = auto_start, repeat, max_attempts
        self.logger = Logger()
        self.tcp_server_socket = None
        self.living_client = {}
        self._connections = set()
        self._threads = set()
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self.ready = threading.Event()
        self.store = None

    @property
    def connection_count(self):
        with self._lock:
            return len(self.living_client)

    def start_server_socket(self):
        sites = load_sites(self.config_dir)
        for site in sites:
            send_encode({"type": "task", "task_id": "0" * 64, "site": site})
        family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
        listener = socket.socket(family, socket.SOCK_STREAM)
        self.tcp_server_socket = listener
        try:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((self.host, self.PORT))
            self.PORT = listener.getsockname()[1]
            listener.listen(self.max_connection)
            listener.settimeout(0.5)
            self.store = TaskStore(self.database_path, max_attempts=self.max_attempts)
            for site in sites:
                self.store.enqueue(site, repeat=self.repeat)
            known_sites = {json.dumps(site, sort_keys=True) for site in sites}
            self.ready.set()
            self.logger.info(f"Listening on {self.host}:{self.PORT}; tasks: {self.store.task_stats()}")
            next_scan = time.monotonic() + 5
            while not self._stop.is_set():
                if time.monotonic() >= next_scan:
                    try:
                        for site in load_sites(self.config_dir):
                            fingerprint = json.dumps(site, sort_keys=True)
                            if fingerprint in known_sites:
                                continue
                            send_encode({"type": "task", "task_id": "0" * 64, "site": site})
                            self.store.enqueue(site)
                            known_sites.add(fingerprint)
                        with self._lock:
                            self._dispatch_locked()
                    except (OSError, ValueError, yaml.YAMLError) as error:
                        self.logger.warn(f"Task directory reload failed: {error}")
                    next_scan = time.monotonic() + 5
                try:
                    client, address = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                client.settimeout(10)
                connection = JsonConnection(client)
                with self._lock:
                    if len(self._connections) >= self.max_connection:
                        connection.close()
                        continue
                    self._connections.add(connection)
                    worker = threading.Thread(
                        target=self._handle_client, args=(address, connection), daemon=True
                    )
                    self._threads.add(worker)
                    worker.start()
        finally:
            self.close()
            if self.store:
                self.store.close()
                self.store = None

    def _dispatch_locked(self):
        if not self.auto_start or self._stop.is_set():
            return
        for owner, node in list(self.living_client.items()):
            if node["task_id"] is not None or not node["ready"]:
                continue
            task = self.store.claim(owner)
            if task is None:
                break
            node["task_id"] = task["task_id"]
            try:
                node["connection"].send(task)
                self.logger.info(f"Assigned {task['task_id'][:12]} to {node['address']}")
            except OSError:
                node["connection"].close()

    def _handle_client(self, address, connection):
        owner = uuid.uuid4().hex
        try:
            auth = connection.receive()
            supplied = auth.get("token")
            if (
                auth.get("type") != "auth"
                or not isinstance(supplied, str)
                or not hmac.compare_digest(supplied.encode(), self.token.encode())
            ):
                connection.send({"type": "auth", "ok": False})
                return
            connection.send({"type": "auth", "ok": True, "protocol": 1})
            connection.socket.settimeout(90)
            with self._lock:
                self.living_client[owner] = {
                    "connection": connection,
                    "address": str(address),
                    "last_seen": time.time(),
                    "status": "connected",
                    "task_id": None,
                    "ready": False,
                }
            self.logger.info(f"Node connected: {address}")
            while not self._stop.is_set():
                message = connection.receive()
                with self._lock:
                    node = self.living_client[owner]
                    node["last_seen"] = time.time()
                    if message["type"] == "ready":
                        node["ready"] = True
                        self._dispatch_locked()
                    elif message["type"] == "task-result":
                        count = self.store.finish(owner, message)
                        node["task_id"] = None
                        node["status"] = {
                            "state": "completed" if not message["errors"] else "failed",
                            "records": count,
                        }
                        self.logger.info(f"Task {message['task_id'][:12]} finished: {count} records")
                        self._dispatch_locked()
                    elif message["type"] == "status":
                        node["status"] = message
                    elif message["type"] != "HB":
                        raise ValueError("Unexpected worker message")
                if message["type"] == "HB":
                    connection.send({"type": "HB", "content": "HB"})
        except (OSError, EOFError, ValueError, KeyError, TypeError) as error:
            if not self._stop.is_set():
                self.logger.warn(f"Node {address}: {error}")
        finally:
            connection.close()
            with self._lock:
                self.living_client.pop(owner, None)
                self._connections.discard(connection)
                if self.store:
                    self.store.release(owner)
                    self._dispatch_locked()
                self._threads.discard(threading.current_thread())

    def send_command(self, command):
        if command != "Start creeper":
            raise ValueError("Only 'Start creeper' is supported; tasks replace legacy file broadcasting")
        with self._lock:
            self.auto_start = True
            self._dispatch_locked()

    def close(self):
        self._stop.set()
        if self.tcp_server_socket:
            self.tcp_server_socket.close()
        with self._lock:
            connections = list(self._connections)
            threads = list(self._threads)
        for connection in connections:
            connection.close()
        for worker in threads:
            if worker is not threading.current_thread():
                worker.join(timeout=5)
