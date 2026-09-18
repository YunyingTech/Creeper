import threading
import time
from copy import deepcopy

from creeper_core.daemon import Daemon
from creeper_core.db_utils import DB
from selenium.common.exceptions import StaleElementReferenceException


class Element:
    def __init__(self, text="中文 O'Reilly", attributes=None):
        self.text = text
        self.attributes = attributes or {"title": "标题", "target": "_blank", "rel": "noopener noreferrer"}

    def get_attribute(self, name):
        return self.attributes.get(name)

    def find_elements(self, by, value):
        return [Element(), Element()]


class Browser:
    def __init__(self, options=None):
        self.closed = False
        self.options = options
        self.url = None
        self.calls = 0

    def set_page_load_timeout(self, timeout):
        self.timeout = timeout

    def get(self, url):
        self.url = url
        time.sleep(0.005)

    def find_elements(self, by, value):
        self.calls += 1
        if "missing" in value:
            return []
        if "stale" in value and self.calls == 1:
            raise StaleElementReferenceException("fixture stale")
        return [Element(), Element()]

    def quit(self):
        self.closed = True


def test_jobs_over_capacity_use_isolated_browsers_and_wait(settings, write_site, site):
    for index in range(7):
        item = deepcopy(site)
        item["url"] = f"https://example.com/{index}"
        write_site(settings["config-dir"], f"site{index}.yaml", item)
    browsers = []
    active = 0
    maximum = 0
    lock = threading.Lock()

    class TrackedBrowser(Browser):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                browsers.append(self)

        def quit(self):
            super().quit()
            nonlocal active
            with lock:
                active -= 1

    daemon = Daemon.from_settings(settings, browser_factory=TrackedBrowser)
    daemon.detect()
    daemon.detect()  # Detection is repeatable, without accumulating class-level state.
    results = daemon.creeper()
    assert len(results) == 7
    assert maximum <= settings["max_thread"]
    assert len({browser.url for browser in browsers}) == 7
    assert all(browser.closed for browser in browsers)
    assert active == 0
    assert not daemon.errors
    with DB(settings["database-path"]) as db:
        assert db.stats()["records"] == 7


def test_failed_collection_is_bounded_and_never_saved(settings, write_site, site):
    site["collections"] = [{"name": "missing", "xpath": "//missing"}, {"name": "valid", "xpath": "//a"}]
    write_site(settings["config-dir"], data=site)
    browsers = []

    def factory(**kwargs):
        browser = Browser(**kwargs)
        browsers.append(browser)
        return browser

    daemon = Daemon.from_settings(settings, max_retries=2, browser_factory=factory)
    results = daemon.creeper()
    assert len(daemon.errors) == 1
    assert daemon.errors[0]["collection"] == "missing"
    assert len(results) == 1
    assert results[0]["collection"] == "valid"
    assert browsers[0].closed
    with DB(settings["database-path"]) as db:
        assert db.stats()["records"] == 1


def test_stale_collection_retries_without_duplicate_writes(settings, write_site, site):
    site["collections"][0]["xpath"] = "//stale"
    write_site(settings["config-dir"], data=site)
    daemon = Daemon.from_settings(settings, browser_factory=Browser)
    assert len(daemon.creeper()) == 1
    assert not daemon.errors
    with DB(settings["database-path"]) as db:
        assert db.stats()["records"] == 1


def test_browser_failure_cleanup(settings, write_site):
    write_site(settings["config-dir"])
    browser = Browser()

    def fail(url):
        raise RuntimeError("page load failed")

    browser.get = fail
    daemon = Daemon.from_settings(settings, browser_factory=lambda **kwargs: browser)
    assert daemon.creeper() == []
    assert daemon.errors
    assert browser.closed


def test_instance_results_do_not_leak(settings):
    first = Daemon.from_settings(settings)
    second = Daemon.from_settings(settings)
    first.result.append({"content": ["isolated"]})
    assert not second.result


def test_sql_failure_does_not_look_like_success(settings, write_site, monkeypatch):
    write_site(settings["config-dir"])

    def fail(self, data):
        raise RuntimeError("disk full")

    monkeypatch.setattr(DB, "save_result", fail)
    daemon = Daemon.from_settings(settings, browser_factory=Browser)
    assert daemon.creeper() == []
    assert daemon.errors[0]["error"] == "disk full"
