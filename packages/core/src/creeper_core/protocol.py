"""CRLF-delimited JSON with bounded frames and serialized socket writes."""

import json
import socket
import threading

MAX_FRAME_BYTES = 4 * 1024 * 1024


def send_encode(command):
    payload = json.dumps(command, ensure_ascii=False, allow_nan=False).encode("utf-8") + b"\r\n"
    if len(payload) > MAX_FRAME_BYTES:
        raise ValueError("Message exceeds the 4 MiB frame limit")
    return payload


class JsonConnection:
    def __init__(self, sock):
        self.socket = sock
        self._buffer = bytearray()
        self._send_lock = threading.Lock()

    def send(self, message):
        payload = send_encode(message)
        with self._send_lock:
            self.socket.sendall(payload)

    def receive(self):
        while True:
            index = self._buffer.find(b"\n")
            if index >= 0:
                if index + 1 > MAX_FRAME_BYTES:
                    raise ValueError("Message exceeds the frame limit")
                frame = bytes(self._buffer[: index + 1])
                del self._buffer[: index + 1]
                message = json.loads(frame)
                if not isinstance(message, dict) or not isinstance(message.get("type"), str):
                    raise ValueError("Protocol messages require a string type field")
                return message
            if len(self._buffer) >= MAX_FRAME_BYTES:
                raise ValueError("Message exceeds the frame limit")
            chunk = self.socket.recv(65536)
            if not chunk:
                if self._buffer:
                    raise ValueError("Connection closed in the middle of a frame")
                raise EOFError("Connection closed")
            self._buffer.extend(chunk)

    def close(self):
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()
