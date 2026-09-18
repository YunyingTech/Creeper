"""Exercise separately installed client/server wheels, real Chrome, and bundled dashboard assets."""

import argparse
import json
import os
import socket
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.request
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        content = '<!doctype html><meta charset="utf-8"><h1>Installed wheel: 中文 O\'Reilly</h1>'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(predicate, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.2)
    raise TimeoutError("Installed-package smoke test timed out")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-python", required=True, type=Path)
    parser.add_argument("--server-python", required=True, type=Path)
    args = parser.parse_args()
    client_python, server_python = str(args.client_python.resolve()), str(args.server_python.resolve())
    env = {**os.environ, "CREEPER_TOKEN": "local-smoke-test", "SE_TIMEOUT": "45", "PYTHONUNBUFFERED": "1"}
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="creeper-installed-") as temporary:
        root = Path(temporary)
        client_dir, server_dir = root / "client", root / "server"
        client_dir.mkdir()
        server_dir.mkdir()
        tasks = server_dir / "config"
        tasks.mkdir()
        http = ThreadingHTTPServer(("127.0.0.1", 0), Page)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        (tasks / "local.yaml").write_text(
            json.dumps(
                {
                    "name": "Wheel smoke",
                    "url": f"http://127.0.0.1:{http.server_port}",
                    "collections": [{"name": "heading", "xpath": "//h1"}],
                }
            ),
            encoding="utf-8",
        )
        tcp_port, web_port = free_port(), free_port()
        processes, logs = [], []

        def launch(python, module, directory, *arguments):
            stream = (directory / (module + ".log")).open("w+", encoding="utf-8")
            logs.append(stream)
            process = subprocess.Popen(
                [python, "-m", module, *arguments],
                cwd=directory,
                env=env,
                stdout=stream,
                stderr=subprocess.STDOUT,
            )
            processes.append(process)
            return process

        def server_ready():
            try:
                with socket.create_connection(("127.0.0.1", tcp_port), timeout=0.2):
                    return True
            except OSError:
                return False

        def complete():
            path = server_dir / "data/server.sqlite3"
            if not path.exists():
                return False
            with closing(sqlite3.connect(path)) as connection:
                return (
                    connection.execute("SELECT COUNT(*) FROM tasks WHERE state='completed'").fetchone()[0]
                    == 1
                )

        try:
            launch(server_python, "creeper_server.cli", server_dir, "--port", str(tcp_port))
            wait_for(server_ready, timeout=15)
            launch(
                client_python,
                "creeper_client.cli",
                client_dir,
                "--server",
                "127.0.0.1",
                "--port",
                str(tcp_port),
            )
            wait_for(complete)
            with closing(sqlite3.connect(server_dir / "data/server.sqlite3")) as connection:
                assert (
                    connection.execute("SELECT content FROM CONTENT").fetchone()[0]
                    == "Installed wheel: 中文 O'Reilly"
                )
                assert connection.execute("SELECT attempts FROM tasks").fetchone()[0] == 1
            launch(server_python, "creeper_server.cli", server_dir, "dashboard", "--port", str(web_port))

            def web_ready():
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{web_port}/api/stats", timeout=1
                    ) as response:
                        return json.load(response)["records"] == 1
                except OSError:
                    return False

            wait_for(web_ready, timeout=15)
            for route in ("/", "/static/dashboard.css", "/static/dashboard.js", "/api/tasks"):
                with urllib.request.urlopen(f"http://127.0.0.1:{web_port}{route}", timeout=3) as response:
                    assert response.status == 200
            print(
                "PASS: independent installed wheels -> authenticated task -> real Chrome -> central SQLite -> dashboard assets"
            )
        except Exception:
            for stream in logs:
                stream.flush()
                stream.seek(0)
                print(stream.read()[-8000:])
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            for stream in logs:
                stream.close()
            http.shutdown()
            http.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    main()
