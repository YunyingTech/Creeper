"""Opt-in local Chrome tests. No external target website is contacted."""

import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest
from creeper_core.daemon import Daemon
from creeper_core.db_utils import DB
from creeper_core.settings import ROOT
from creeper_server.dashboard import Dashboard
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

pytestmark = pytest.mark.skipif(
    os.environ.get("CREEPER_BROWSER_TESTS") != "1",
    reason="Set CREEPER_BROWSER_TESTS=1 to run local Chrome integration tests",
)


def test_real_chrome_crawl_and_dashboard(settings, write_site, site, tmp_path):
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT / "examples/site"))
    http = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    site["url"] = f"http://127.0.0.1:{http.server_port}"
    site["pre"] = [
        {"type": "input", "xpath": "//*[@id='keyword']", "text": "Creeper"},
        {"type": "click", "xpath": "//*[@id='reveal']"},
        {"type": "scroll", "pixels": 10},
        {"type": "wait", "seconds": 0.01},
    ]
    site["collections"] = [
        {"name": "tags", "xpath": "//*[@id='news']", "type": "tag", "child": "a"},
        {"name": "attribute", "xpath": "//*[@id='news']//a/@title"},
        {"name": "descendant attributes", "xpath": "//*[@id='news']//@title"},
        {"name": "target", "xpath": "//*[@id='news']", "type": "target", "child": "_blank"},
        {"name": "rel", "xpath": "//*[@id='news']", "type": "rel", "child": "noreferrer"},
        {"name": "class", "xpath": "//body", "type": "class", "child": "summary"},
        {"name": "css", "xpath": "//body", "type": "css", "child": "#news a"},
        {"name": "xpath", "xpath": "//body", "type": "xpath", "child": ".//a"},
        {"name": "clicked", "xpath": "//*[@id='delayed']"},
        {"name": "typed", "xpath": "//*[@id='keyword']", "attribute": "value"},
    ]
    write_site(settings["config-dir"], data=site)
    settings["timeout"] = 3
    try:
        daemon = Daemon.from_settings(settings)
        results = daemon.creeper()
        assert not daemon.errors
        assert len(results) == 10
        assert results[1]["content"] == ["第一条标题", "O'Reilly 与中文"]
        assert results[2]["content"] == results[1]["content"]
        assert results[-1]["content"] == ["Creeper"]
        with DB(settings["database-path"]) as db:
            assert db.stats()["records"] == 17
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)

    app = Dashboard(settings["database-path"]).app
    server = make_server("127.0.0.1", 0, app, threaded=True)
    dashboard_thread = threading.Thread(target=server.serve_forever, daemon=True)
    dashboard_thread.start()
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    browser = None
    try:
        browser = webdriver.Chrome(options=options)
        browser.get(f"http://127.0.0.1:{server.server_port}")
        wait = WebDriverWait(browser, 5)
        wait.until(lambda driver: driver.find_element(By.ID, "records").text == "17")
        browser.find_element(By.ID, "query").send_keys("O'Reilly")
        browser.find_element(By.CSS_SELECTOR, "#search-form button").click()
        wait.until(lambda driver: "2 条匹配" in driver.find_element(By.ID, "message").text)
        assert len(browser.find_elements(By.CSS_SELECTOR, "#rows tr")) == 2
        browser.set_window_size(390, 844)
        assert browser.execute_script("return document.documentElement.scrollWidth <= window.innerWidth")
        screenshots = ROOT / "data" / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        browser.save_screenshot(str(screenshots / "dashboard-mobile.png"))
        browser.set_window_size(1440, 1000)
        browser.save_screenshot(str(screenshots / "dashboard-desktop.png"))
    finally:
        if browser:
            browser.quit()
        server.shutdown()
        server.server_close()
        dashboard_thread.join(timeout=2)
