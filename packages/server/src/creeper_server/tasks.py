"""Durable jobs and atomic central result commits."""

import datetime
import hashlib
import json
import uuid

from creeper_core.db_utils import DB
from creeper_core.settings import validate_site


class TaskStore(DB):
    def __init__(self, path, max_attempts=3):
        super().__init__(path)
        self.max_attempts = max_attempts
        with self._lock, self.connection:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, payload TEXT NOT NULL, "
                "state TEXT NOT NULL DEFAULT 'pending', owner TEXT, attempts INTEGER NOT NULL DEFAULT 0, "
                "error TEXT, created_at TEXT NOT NULL, finished_at TEXT)"
            )
            # The server process owns all leases. Restarted tasks return to the queue.
            self.connection.execute(
                "UPDATE tasks SET state = CASE WHEN attempts < ? THEN 'pending' ELSE 'failed' END, owner = NULL "
                "WHERE state = 'running'",
                (max_attempts,),
            )

    def enqueue(self, site, repeat=False):
        site = validate_site(site)
        payload = json.dumps(site, ensure_ascii=False, sort_keys=True)
        task_id = uuid.uuid4().hex if repeat else hashlib.sha256(payload.encode()).hexdigest()
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO tasks (id, payload, created_at) VALUES (?, ?, ?)",
                (task_id, payload, datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )
        return task_id

    def claim(self, owner):
        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT id, payload FROM tasks WHERE state = 'pending' ORDER BY created_at, id LIMIT 1"
            ).fetchone()
            if not row:
                return None
            self.connection.execute(
                "UPDATE tasks SET state = 'running', owner = ?, attempts = attempts + 1 WHERE id = ?",
                (owner, row["id"]),
            )
        return {"type": "task", "task_id": row["id"], "site": json.loads(row["payload"])}

    def release(self, owner):
        with self._lock, self.connection:
            self.connection.execute(
                "UPDATE tasks SET state = CASE WHEN attempts < ? THEN 'pending' ELSE 'failed' END, "
                "owner = NULL, error = 'Worker disconnected before completion' WHERE owner = ? AND state = 'running'",
                (self.max_attempts, owner),
            )

    def finish(self, owner, message):
        task_id = message.get("task_id")
        results, errors = message.get("results"), message.get("errors")
        if not isinstance(task_id, str) or not isinstance(results, list) or not isinstance(errors, list):
            raise ValueError("task-result requires task_id, results and errors")
        with self._lock, self.connection:
            task = self.connection.execute(
                "SELECT payload FROM tasks WHERE id = ? AND owner = ? AND state = 'running'", (task_id, owner)
            ).fetchone()
            if not task:
                raise ValueError("Result does not belong to this worker's active task")
            site = json.loads(task["payload"])
            allowed = {collection["name"] for collection in site["collections"]}
            rows = []
            for result in results:
                if (
                    not isinstance(result, dict)
                    or result.get("url") != site["url"]
                    or result.get("collection") not in allowed
                    or not isinstance(result.get("content"), list)
                    or not all(isinstance(text, str) for text in result["content"])
                ):
                    raise ValueError("Invalid task result data")
                date = datetime.datetime.fromisoformat(result["Date"]).isoformat(sep=" ", timespec="seconds")
                rows.extend((date, text, result["url"], result["collection"]) for text in result["content"])
            self.connection.executemany(
                "INSERT INTO CONTENT (date, content, url, collection) VALUES (?, ?, ?, ?)", rows
            )
            self.connection.execute(
                "UPDATE tasks SET state = ?, owner = NULL, error = ?, finished_at = ? WHERE id = ?",
                (
                    "partial-failure" if errors and results else "failed" if errors else "completed",
                    json.dumps(errors, ensure_ascii=False) if errors else None,
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    task_id,
                ),
            )
        return len(rows)

    def task_stats(self):
        with self._lock:
            rows = self.connection.execute(
                "SELECT state, COUNT(*) AS count FROM tasks GROUP BY state"
            ).fetchall()
        return {row["state"]: row["count"] for row in rows}
