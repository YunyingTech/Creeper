import threading
import time

from creeper_client.client import Client
from creeper_client.processor import Processor
from creeper_core.daemon import Daemon
from creeper_core.db_utils import DB
from creeper_server.server import Server

from tests.test_daemon import Browser


def test_server_to_worker_to_database(settings, write_site, tmp_path):
    write_site(settings["server-config-dir"])
    server = Server(
        0,
        token="fixture-token",
        config_dir=settings["server-config-dir"],
        auto_start=True,
        database_path=tmp_path / "server.sqlite3",
    )
    server_thread = threading.Thread(target=server.start_server_socket)
    server_thread.start()
    assert server.ready.wait(3)
    settings["auth-token"] = "fixture-token"
    client = Client("127.0.0.1", server.PORT, settings=settings, retry_delay=0)
    client.processor = Processor(
        settings,
        report=client._report,
        daemon_factory=lambda settings, **kwargs: Daemon.from_settings(
            settings, browser_factory=Browser, **kwargs
        ),
    )
    client_thread = threading.Thread(target=client.connect_to_server)
    client_thread.start()
    try:
        deadline = time.monotonic() + 5
        completed = False
        while time.monotonic() < deadline:
            with server._lock:
                states = [item["status"] for item in server.living_client.values()]
            if any(isinstance(state, dict) and state.get("state") == "completed" for state in states):
                completed = True
                break
            time.sleep(0.01)
        assert completed
        with DB(settings["database-path"]) as db:
            assert db.stats()["records"] == 1
        assert server.store.stats()["records"] == 1
        assert server.store.task_stats() == {"completed": 1}
    finally:
        client.close_socket()
        client_thread.join(timeout=5)
        server.close()
        server_thread.join(timeout=3)
    assert not client_thread.is_alive()
    assert not server_thread.is_alive()


def test_client_refused_connection_has_bounded_retries(settings):
    import socket

    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    # A bound but non-listening socket rejects connections without a race for port allocation.
    try:
        client = Client("127.0.0.1", port, settings=settings, retry_delay=0)
        assert client.connect_to_server() is False
    finally:
        listener.close()


def test_two_workers_share_jobs_and_hot_reload_without_repeat(settings, write_site, site, tmp_path):
    from copy import deepcopy

    for index in range(4):
        config = deepcopy(site)
        config["url"] = f"https://example.com/task-{index}"
        write_site(settings["server-config-dir"], f"{index}.yaml", config)
    server = Server(
        0,
        token="token",
        config_dir=settings["server-config-dir"],
        database_path=tmp_path / "server.sqlite3",
        repeat=True,
    )
    server_thread = threading.Thread(target=server.start_server_socket)
    server_thread.start()
    assert server.ready.wait(3)
    settings["auth-token"] = "token"
    clients, threads, seen = [], [], [[], []]
    barrier = threading.Barrier(2)

    def browser_factory(index):
        class NodeBrowser(Browser):
            def get(self, url):
                seen[index].append(url)
                if len(seen[index]) == 1:
                    barrier.wait(timeout=3)
                super().get(url)

        return NodeBrowser

    try:
        for index in range(2):
            node_settings = {**settings, "database-path": str(tmp_path / f"node-{index}.sqlite3")}
            client = Client("127.0.0.1", server.PORT, settings=node_settings, retry_delay=0)
            factory = browser_factory(index)
            client.processor = Processor(
                node_settings,
                report=client._report,
                daemon_factory=lambda config, factory=factory, **kwargs: Daemon.from_settings(
                    config, browser_factory=factory, **kwargs
                ),
            )
            clients.append(client)
            thread = threading.Thread(target=client.connect_to_server)
            threads.append(thread)
            thread.start()
        deadline = time.monotonic() + 5
        while server.store.task_stats().get("completed", 0) < 4 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.store.task_stats() == {"completed": 4}
        assert all(seen)
        assert len(set(seen[0] + seen[1])) == 4
        assert len(seen[0] + seen[1]) == 4
        changed = deepcopy(site)
        changed["url"] = "https://example.com/new-task"
        write_site(settings["server-config-dir"], "new.yaml", changed)
        deadline = time.monotonic() + 8
        while server.store.task_stats().get("completed", 0) < 5 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.store.task_stats() == {"completed": 5}
        assert server.store.stats()["records"] == 5
    finally:
        for client in clients:
            client.close_socket()
        for thread in threads:
            thread.join(timeout=5)
        server.close()
        server_thread.join(timeout=3)
    assert all(not thread.is_alive() for thread in threads)
