"""Bounded Selenium jobs with one browser per site and explicit resource ownership."""

import datetime
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from creeper_core.db_utils import DB
from creeper_core.logger import Logger
from creeper_core.settings import ROOT, load_sites, number


class CrawlCancelled(Exception):
    pass


class Daemon:
    MAX_RETRY_COUNT = 3

    def __init__(
        self,
        max_thread=2,
        delay=1,
        proxy=False,
        *,
        config_path=None,
        database_path=None,
        timeout=15,
        page_load_timeout=45,
        max_retries=3,
        headless=True,
        database_backend="sqlite",
        mysql_config=None,
        browser_factory=None,
    ):
        number(max_thread, "max_thread", 1, integer=True)
        number(delay, "delay")
        number(max_retries, "max_retries", 1, integer=True)
        self.max_thread = max_thread
        self.delay = delay
        self.proxy = proxy
        self.proxy_list = []
        self.config_path = Path(config_path or ROOT / "config")
        self.database_path = database_path or ROOT / "data/creeper.sqlite3"
        self.database_backend = database_backend
        self.mysql_config = mysql_config or ROOT / "database.yaml"
        self.timeout = timeout
        self.page_load_timeout = page_load_timeout
        self.max_retries = max_retries
        self.headless = headless
        self.browser_factory = browser_factory or webdriver.Chrome
        self.logger = Logger()
        self.yaml_loaded_data = []
        self.url_list = []
        self.result = []
        self.errors = []
        self.db = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    @classmethod
    def from_settings(cls, settings, **overrides):
        options = dict(
            max_thread=settings["max_thread"],
            delay=settings["delay"],
            proxy=settings["IP-pool"],
            config_path=settings["config-dir"],
            database_path=settings["database-path"],
            timeout=settings["timeout"],
            page_load_timeout=settings["page-load-timeout"],
            max_retries=settings["max-retries"],
            headless=settings["headless"],
            database_backend=settings["database-backend"],
            mysql_config=settings["mysql-config"],
        )
        options.update(overrides)
        daemon = cls(**options)
        if daemon.proxy:
            for path in settings["IP-pool-list"]:
                daemon.load_proxy_list(path)
            if not daemon.proxy_list:
                raise ValueError("IP-pool enabled but no proxy addresses were found")
        return daemon

    def load_proxy_list(self, path):
        with Path(path).open(encoding="utf-8") as stream:
            for line in stream:
                address = line.strip()
                if address and not address.startswith("#"):
                    if "://" not in address:
                        address = "http://" + address
                    self.proxy_list.append(address)

    def detect(self, filenames=None):
        self.yaml_loaded_data = load_sites(self.config_path, filenames)
        self.url_list = [site["url"] for site in self.yaml_loaded_data]
        return self.yaml_loaded_data

    def stop(self):
        self._stop.set()

    def _pause(self, seconds):
        if self._stop.wait(seconds):
            raise CrawlCancelled()

    def creeper(self):
        if not self.yaml_loaded_data:
            self.detect()
        if self.proxy and not self.proxy_list:
            raise ValueError("Proxy pool is empty")
        self.result.clear()
        self.errors.clear()
        if self.database_backend == "mysql":
            from creeper_core.mysql_connector import MysqlConnector

            self.db = MysqlConnector(self.mysql_config)
        elif self.database_backend == "sqlite":
            self.db = DB(self.database_path)
        else:
            raise ValueError("Unsupported database backend")
        executor = ThreadPoolExecutor(max_workers=self.max_thread, thread_name_prefix="creeper")
        try:
            futures = [
                executor.submit(self._crawl_site, site, index)
                for index, site in enumerate(self.yaml_loaded_data)
            ]
            for future in as_completed(futures):
                future.result()
        except KeyboardInterrupt:
            self.stop()
            raise
        finally:
            executor.shutdown(wait=True, cancel_futures=True)
            self.db.close()
            self.db = None
        return self.result

    def _error(self, site, collection, error):
        item = {"url": site["url"], "collection": collection, "error": str(error)}
        with self._lock:
            self.errors.append(item)
        self.logger.error(f"{site['url']} [{collection}]: {error}")

    def _crawl_site(self, site, index):
        browser = None
        try:
            self._pause(0)
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--window-size=1440,1000")
            if self.proxy:
                options.add_argument("--proxy-server=" + self.proxy_list[index % len(self.proxy_list)])
            browser = self.browser_factory(options=options)
            browser.set_page_load_timeout(self.page_load_timeout)
            self.logger.info(f"Crawling {site['url']}")
            browser.get(site["url"])
            for operation in sorted(site.get("pre", []), key=lambda op: op.get("id", 0)):
                self._pre_operation(browser, operation)
            for position, collection in enumerate(site["collections"]):
                self._pause(self.delay if position else 0)
                for attempt in range(self.max_retries):
                    try:
                        content = self._extract(browser, collection)
                        record = {
                            "Date": datetime.datetime.now(datetime.timezone.utc),
                            "content": content,
                            "url": site["url"],
                            "collection": collection["name"],
                        }
                        self.db.save_result(record)
                        with self._lock:
                            self.result.append(record)
                        break
                    except (StaleElementReferenceException, TimeoutException) as error:
                        if attempt + 1 == self.max_retries:
                            self._error(site, collection["name"], error)
                        else:
                            self._pause(self.delay)
                    except WebDriverException as error:
                        self._error(site, collection["name"], error)
                        break
        except CrawlCancelled:
            self.logger.info(f"Cancelled {site['url']}")
        except Exception as error:
            self._error(site, "site", error)
        finally:
            if browser is not None:
                try:
                    browser.quit()
                except WebDriverException as error:
                    self.logger.warn(f"Browser cleanup: {error}")

    def _pre_operation(self, browser, operation):
        self._pause(0)
        kind = operation["type"]
        if kind == "wait":
            self._pause(operation.get("seconds", 1))
        elif kind == "scroll":
            browser.execute_script("window.scrollBy(0, arguments[0]);", operation.get("pixels", 600))
        else:
            element = WebDriverWait(browser, self.timeout).until(
                EC.element_to_be_clickable((By.XPATH, operation["xpath"]))
            )
            if kind == "click":
                element.click()
            else:
                element.clear()
                element.send_keys(operation["text"])

    def _extract(self, browser, collection):
        xpath = collection["xpath"]
        attribute = collection.get("attribute")
        # Selenium returns elements only; translate terminal /@name and //@name to element selection.
        match = re.search(r"(/+?)@([\w:.-]+)$", xpath)
        if match:
            attribute = attribute or match.group(2)
            xpath = xpath[: match.start()] + ("//*" if match.group(1) == "//" else "")
        kind = collection.get("type", "text")

        def read_content(driver):
            self._pause(0)
            roots = driver.find_elements(By.XPATH, xpath)
            elements = []
            for root in roots:
                if kind == "text":
                    elements.append(root)
                elif kind in ("target", "rel"):
                    candidates = [root, *root.find_elements(By.CSS_SELECTOR, f"[{kind}]")]
                    for element in candidates:
                        value = element.get_attribute(kind) or ""
                        if (
                            collection["child"] in value.split()
                            if kind == "rel"
                            else value == collection["child"]
                        ):
                            elements.append(element)
                else:
                    selector = {
                        "class": By.CLASS_NAME,
                        "tag": By.TAG_NAME,
                        "css": By.CSS_SELECTOR,
                        "xpath": By.XPATH,
                    }[kind]
                    elements.extend(root.find_elements(selector, collection["child"]))
            values = [
                (element.get_attribute(attribute) if attribute else element.text) or ""
                for element in elements
            ]
            # Deduplicate within a collection, preserving source order.
            return list(dict.fromkeys(value.strip() for value in values if value.strip())) or False

        return WebDriverWait(browser, self.timeout, poll_frequency=0.2).until(read_content)
