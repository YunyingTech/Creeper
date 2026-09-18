import datetime

import pytest
from creeper_server.tasks import TaskStore


def result(task, text="中文 O'Reilly", errors=None):
    return {
        "task_id": task["task_id"],
        "results": [
            {
                "url": task["site"]["url"],
                "collection": task["site"]["collections"][0]["name"],
                "Date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "content": [text],
            }
        ],
        "errors": errors or [],
    }


def test_each_job_is_leased_to_one_worker_and_results_are_atomic(tmp_path, site):
    with TaskStore(tmp_path / "server.sqlite3") as store:
        store.enqueue(site)
        task = store.claim("worker-a")
        assert store.claim("worker-b") is None
        with pytest.raises(ValueError):
            store.finish("worker-b", result(task))
        assert store.stats()["records"] == 0
        store.finish("worker-a", result(task))
        assert store.task_stats() == {"completed": 1}
        assert store.stats()["records"] == 1
        with pytest.raises(ValueError):
            store.finish("worker-a", result(task))
        assert store.stats()["records"] == 1


def test_disconnect_retries_are_bounded(tmp_path, site):
    with TaskStore(tmp_path / "server.sqlite3", max_attempts=2) as store:
        store.enqueue(site)
        first = store.claim("a")
        store.release("a")
        second = store.claim("b")
        assert second["task_id"] == first["task_id"]
        store.release("b")
        assert store.claim("c") is None
        assert store.task_stats() == {"failed": 1}


def test_restart_recovers_leases_and_deduplicates_existing_tasks(tmp_path, site):
    path = tmp_path / "server.sqlite3"
    with TaskStore(path) as store:
        task_id = store.enqueue(site)
        store.claim("old-session")
    with TaskStore(path) as store:
        assert store.enqueue(site) == task_id
        task = store.claim("new-session")
        assert task["task_id"] == task_id
        store.finish("new-session", result(task))
    with TaskStore(path) as store:
        store.enqueue(site)
        assert store.claim("next") is None
        assert store.enqueue(site, repeat=True) != task_id
        assert store.claim("next")


def test_partial_failure_keeps_successful_collection(tmp_path, site):
    with TaskStore(tmp_path / "server.sqlite3") as store:
        store.enqueue(site)
        task = store.claim("a")
        store.finish("a", result(task, errors=[{"error": "another collection failed"}]))
        assert store.task_stats() == {"partial-failure": 1}
        assert store.stats()["records"] == 1


def test_invalid_result_rolls_back_all_content(tmp_path, site):
    with TaskStore(tmp_path / "server.sqlite3") as store:
        store.enqueue(site)
        task = store.claim("a")
        message = result(task)
        message["results"].append({"url": "https://unexpected.example"})
        with pytest.raises(ValueError):
            store.finish("a", message)
        assert store.stats()["records"] == 0
        assert store.task_stats() == {"running": 1}
