import datetime
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from creeper_core.db_utils import DB
from creeper_server.dashboard import Dashboard


def record(content):
    return {
        "Date": datetime.datetime.now(datetime.timezone.utc),
        "content": content,
        "url": "https://example.com",
        "collection": "新闻",
    }


def test_sqlite_quotes_unicode_and_threaded_writes(tmp_path):
    with DB(tmp_path / "test.sqlite3") as db:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(
                pool.map(
                    lambda _: db.save_result(record(["O'Reilly", "中文; DROP TABLE CONTENT;", "100%_"])),
                    range(10),
                )
            )
        assert db.stats()["records"] == 30
        assert db.stats()["sources"] == 1
        assert db.list_results(query="O'Reilly")["total"] == 10
        assert db.list_results(query="%_")["total"] == 10
        assert len(db.list_results(limit=2, offset=2)["items"]) == 2


def test_legacy_database_migration(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE CONTENT (id INTEGER PRIMARY KEY, date DATETIME, content varchar(4096))"
        )
        connection.execute("INSERT INTO CONTENT VALUES (1, '2024-01-01', 'legacy')")
    with DB(path) as db:
        assert db.list_results()["items"][0]["content"] == "legacy"
        db.save_result(record(["new"]))
        assert db.stats()["records"] == 2


def test_dashboard_empty_populated_and_validation(tmp_path):
    path = tmp_path / "dashboard.sqlite3"
    dashboard = Dashboard(path)
    client = dashboard.app.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/static/dashboard.js").status_code == 200
    assert client.get("/api/stats").json["records"] == 0
    assert client.get("/api/results").json["items"] == []
    with DB(path) as db:
        db.save_result(record(["<script>alert(1)</script>", "中文"]))
    assert client.get("/api/results?q=中文").json["total"] == 1
    assert (
        client.get("/api/results?limit=1&offset=1").json["items"][0]["content"] == "<script>alert(1)</script>"
    )
    for query in ("limit=0", "limit=201", "offset=-1", "limit=x", "q=" + "x" * 501):
        assert client.get("/api/results?" + query).status_code == 400
    assert "frame-ancestors 'none'" in client.get("/").headers["Content-Security-Policy"]
