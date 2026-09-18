import base64
import socket
import threading
import time

import pytest
from creeper_client.processor import Processor
from creeper_core.protocol import JsonConnection, send_encode
from creeper_server.server import Server


def test_fragmented_unicode_and_multiple_frames():
    left, right = socket.socketpair()
    receiver = JsonConnection(left)
    message = {"type": "file", "content": "中文" * 2000}
    payload = send_encode(message) + send_encode({"type": "HB"})

    def send_chunks():
        for offset in range(0, len(payload), 7):
            right.sendall(payload[offset : offset + 7])
        right.close()

    sender = threading.Thread(target=send_chunks)
    sender.start()
    try:
        assert receiver.receive() == message
        assert receiver.receive() == {"type": "HB"}
        with pytest.raises(EOFError):
            receiver.receive()
    finally:
        receiver.close()
        sender.join(timeout=2)


@pytest.mark.parametrize("payload", [b"[]\n", b"{}\n", b"not json\n", b'{"type": "HB"'])
def test_malformed_or_truncated_frames(payload):
    left, right = socket.socketpair()
    receiver = JsonConnection(left)
    right.sendall(payload)
    right.close()
    try:
        with pytest.raises(ValueError):
            receiver.receive()
    finally:
        receiver.close()


def test_frame_size_limit(monkeypatch):
    import creeper_core.protocol as protocol

    monkeypatch.setattr(protocol, "MAX_FRAME_BYTES", 32)
    with pytest.raises(ValueError):
        protocol.send_encode({"type": "x", "content": "a" * 100})
    left, right = socket.socketpair()
    receiver = JsonConnection(left)
    right.sendall(b"x" * 33)
    try:
        with pytest.raises(ValueError):
            receiver.receive()
    finally:
        receiver.close()
        right.close()


@pytest.mark.parametrize(
    "filename", ["../escape.yaml", "C:\\escape.yaml", "/tmp/a.yaml", "a.py", "a.yaml:stream", "NUL.yaml"]
)
def test_file_transfer_rejects_paths(settings, filename):
    processor = Processor(settings)
    with pytest.raises(ValueError):
        processor.process_file_command({"filename": filename, "content": ""})


def test_file_transfer_validated_and_atomic(settings, write_site, tmp_path):
    source = write_site(tmp_path)
    processor = Processor(settings)
    encoded = base64.b64encode(source.read_bytes()).decode()
    processor.process_file_command({"filename": "site.yaml", "content": encoded})
    destination = processor.directory / "site.yaml"
    assert destination.read_bytes() == source.read_bytes()
    with pytest.raises(ValueError):
        processor.process_file_command(
            {"filename": "site.yaml", "content": base64.b64encode(b"url: bad").decode()}
        )
    assert destination.read_bytes() == source.read_bytes()


def test_server_authentication_assignment_and_disconnect(settings, write_site, tmp_path):
    write_site(settings["server-config-dir"])
    server = Server(
        0, token="secret", config_dir=settings["server-config-dir"], database_path=tmp_path / "server.sqlite3"
    )
    worker = threading.Thread(target=server.start_server_socket)
    worker.start()
    assert server.ready.wait(3)
    connection = None
    try:
        bad = JsonConnection(socket.create_connection(("127.0.0.1", server.PORT), timeout=2))
        bad.send({"type": "auth", "token": "wrong"})
        assert bad.receive() == {"type": "auth", "ok": False}
        with pytest.raises(EOFError):
            bad.receive()
        bad.close()
        connection = JsonConnection(socket.create_connection(("127.0.0.1", server.PORT), timeout=2))
        connection.send({"type": "auth", "token": "secret"})
        assert connection.receive()["ok"]
        connection.send({"type": "ready"})
        task = connection.receive()
        assert task["type"] == "task"
        assert task["site"]["name"] == "fixture"
        connection.send({"type": "HB"})
        assert connection.receive()["type"] == "HB"
        assert server.connection_count == 1
        connection.close()
        deadline = time.monotonic() + 2
        while server.connection_count and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.connection_count == 0
        assert server.store.task_stats() == {"pending": 1}
    finally:
        if connection:
            connection.close()
        server.close()
        worker.join(timeout=3)
    assert not worker.is_alive()


def test_remote_bind_requires_token():
    with pytest.raises(ValueError, match="requires"):
        Server(0, host="0.0.0.0")
