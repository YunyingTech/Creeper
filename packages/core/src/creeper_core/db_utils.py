"""SQLite persistence. Legacy CONTENT tables migrate in place."""

import sqlite3
from pathlib import Path
from threading import RLock


class DB:
    DEFAULT_TABLE = "CONTENT"

    def __init__(self, path):
        self.db_path = str(path)
        if self.db_path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self.connection = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS CONTENT (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "date TEXT, content TEXT, url TEXT DEFAULT '', collection TEXT DEFAULT '')"
        )
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(CONTENT)")}
        for column in ("url", "collection"):
            if column not in columns:
                self.connection.execute(f"ALTER TABLE CONTENT ADD COLUMN {column} TEXT DEFAULT ''")
        self.connection.commit()

    def save_result(self, data):
        date = data["Date"].isoformat(sep=" ", timespec="seconds")
        rows = [(date, text, data.get("url", ""), data.get("collection", "")) for text in data["content"]]
        with self._lock, self.connection:
            self.connection.executemany(
                "INSERT INTO CONTENT (date, content, url, collection) VALUES (?, ?, ?, ?)", rows
            )
        return len(rows)

    def list_results(self, limit=50, offset=0, query=""):
        where = (
            " WHERE instr(content, ?) > 0 OR instr(url, ?) > 0 OR instr(collection, ?) > 0" if query else ""
        )
        params = (query, query, query) if query else ()
        with self._lock:
            total = self.connection.execute("SELECT COUNT(*) FROM CONTENT" + where, params).fetchone()[0]
            rows = self.connection.execute(
                "SELECT id, date, content, url, collection FROM CONTENT"
                + where
                + " ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return {"total": total, "items": [dict(row) for row in rows], "limit": limit, "offset": offset}

    def stats(self):
        with self._lock:
            row = self.connection.execute(
                "SELECT COUNT(*) AS records, COUNT(DISTINCT NULLIF(url, '')) AS sources, MAX(date) AS latest FROM CONTENT"
            ).fetchone()
        return dict(row)

    def task_stats(self):
        with self._lock:
            exists = self.connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'tasks'").fetchone()
            if not exists:
                return {}
            rows = self.connection.execute(
                "SELECT state, COUNT(*) AS count FROM tasks GROUP BY state"
            ).fetchall()
        return {row["state"]: row["count"] for row in rows}

    def close(self):
        with self._lock:
            self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
