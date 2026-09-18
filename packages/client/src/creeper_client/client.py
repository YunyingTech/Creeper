"""TCP collection worker with bounded connection retries and heartbeat liveness."""

import socket
import threading

import yaml
from creeper_core.logger import Logger
from creeper_core.protocol import JsonConnection
from creeper_core.settings import load_settings

from creeper_client.processor import Processor


class Client:
    MAX_RETRY_COUNT = 3

    def __init__(self, IP, PORT, settings=None, processor=None, retry_delay=5):
        self.IP, self.PORT = IP, PORT
        self.settings = settings or load_settings()
        self.logger = Logger()
        self.client_socket = None
        self.connection = None
        self.server_living = False
        self.retry_delay = retry_delay
        self._stop = threading.Event()
        self.processor = processor or Processor(self.settings, report=self._report)

    def _report(self, message):
        connection = self.connection
        if connection:
            try:
                connection.send(message)
            except OSError:
                self.logger.warn("Could not report task status: connection lost")

    def connect_to_server(self):
        failures = 0
        try:
            while not self._stop.is_set() and failures < self.MAX_RETRY_COUNT:
                connection = None
                heartbeat = None
                session_stop = threading.Event()
                try:
                    self.client_socket = socket.create_connection((self.IP, self.PORT), timeout=10)
                    self.client_socket.settimeout(90)
                    connection = JsonConnection(self.client_socket)
                    connection.send({"type": "auth", "token": self.settings["auth-token"]})
                    response = connection.receive()
                    if response.get("type") != "auth" or response.get("ok") is not True:
                        self.logger.error("Server authentication rejected")
                        return False
                    self.connection = connection
                    self.server_living = True
                    self.logger.info("Connected to server")
                    heartbeat = threading.Thread(
                        target=self._heartbeat, args=(connection, session_stop), daemon=True
                    )
                    heartbeat.start()
                    connection.send({"type": "ready"})
                    while not self._stop.is_set():
                        message = connection.receive()
                        if message["type"] != "HB":
                            try:
                                self.processor.process_command(message)
                            except (ValueError, KeyError, OSError, yaml.YAMLError) as error:
                                if message["type"] == "task":
                                    self._report(
                                        {
                                            "type": "task-result",
                                            "task_id": message.get("task_id"),
                                            "results": [],
                                            "errors": [{"error": str(error)}],
                                        }
                                    )
                                else:
                                    self._report({"type": "status", "state": "rejected", "error": str(error)})
                except (OSError, EOFError, ValueError) as error:
                    if not self._stop.is_set():
                        failures += 1
                        self.logger.warn(f"Connection lost ({failures}/{self.MAX_RETRY_COUNT}): {error}")
                finally:
                    session_stop.set()
                    self.server_living = False
                    self.connection = None
                    if connection:
                        connection.close()
                    if heartbeat:
                        heartbeat.join(timeout=2)
                    self.processor.reset_session()
                if not self._stop.is_set() and failures < self.MAX_RETRY_COUNT:
                    self._stop.wait(self.retry_delay)
            return self._stop.is_set()
        finally:
            self.close_socket()
            self.processor.close()

    def _heartbeat(self, connection, stop):
        try:
            while not stop.is_set() and not self._stop.is_set():
                connection.send({"type": "HB", "content": "HB"})
                stop.wait(20)
        except OSError:
            connection.close()

    def close_socket(self):
        self._stop.set()
        if self.connection:
            self.connection.close()
        elif self.client_socket:
            self.client_socket.close()
