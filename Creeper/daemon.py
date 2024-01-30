import datetime
import threading
import time

import selenium.common.exceptions
from selenium import webdriver
import os
import yaml
from selenium.webdriver.common.by import By
import queue

from Logger.Logger import Logger
from Utils.db_utils import DB


class Daemon:
    # 定义基础目录
    BASE_DIR = "./"
    # 定义配置文件路径
    config_path = "config"
    # 定义url列表
    url_list = []
    # 定义yaml加载数据
    yaml_loaded_data = []
    # 定义结果
    result = []
    # 定义url配置
    url_config = {}
    # 定义最大重试次数
    MAX_RETRY_COUNT = 3

    def __init__(self, max_thread=100, delay=1, proxy=False):
        """

        :param max_thread: 最大同时爬取线程数
        :param delay: 爬取各个Collection之间的延迟间隔
        :param proxy: 是否启动代理池
        """
        # 设置浏览器选项
        self.browser_options = webdriver.ChromeOptions()
        self.browser_options.add_argument("--headless")
        # 设置日志
        self.logger = Logger()
        # 设置浏览器
        self.browser = webdriver.Chrome(options=self.browser_options)
        # 设置最大线程数
        self.max_thread = max_thread
        # 设置延迟
        self.delay = delay
        # 设置代理池
        self.proxy = proxy
        # 设置数据库
        self.db = DB('db.sqlite3')
        # 判断是否启动代理池
        if proxy:
            self.logger.warn("Don't forget to load proxy list by 'load_proxy_list()' function")
        # 定义代理列表
        self.proxy_list = []

    def load_proxy_list(self, path):
        """

        :param path: 代理池列表路径
        :return:
        """
        self.proxy_list = ["--proxy-server=http://" + line for line in open(path, "r").readlines()]

    def detect(self):
        """
        检测需要爬取的网页配置文件的项目
        :return:
        """
        config_file_list = os.listdir(self.config_path)
        for i in config_file_list:
            self._test_and_load_config_file(i)
        for i in self.yaml_loaded_data:
            self.url_list.append(i["url"])
            self.url_config.update({i["url"]: i})

    def _test_and_load_config_file(self, path):
        """
        测试并加载配置文件
        :param path: 配置文件的路径
        :return:
        """
        try:
            data = yaml.load(open(os.path.join(self.config_path, path), "r", encoding="utf8"), Loader=yaml.FullLoader)
            self.yaml_loaded_data.append(data)
            return True
        except Exception as e:
            print(e)
            return False

    def creeper(self):
        """
        爬取主线程
        :return:
        """
        try:
            thread_queue = queue.Queue(maxsize=self.max_thread)
            for url in self.url_list:
                th = threading.Thread(target=self.creeper_threading, args=(url,))
                thread_queue.put(th)
            while not thread_queue.empty():
                th = thread_queue.get()
                # th.setDaemon(True)
                th.start()
                time.sleep(int(self.delay))
        except selenium.common.exceptions.NoSuchElementException as e:
            self.logger.warn(url + " has no such Element,Skip......")

    def creeper_threading(self, url):
        """
        爬取子线程
        :param url:
        :return:
        """
        self.logger.info("Start crawling pages " + url)
        config = self.url_config[url]
        collection = config["collections"]
        self.browser.get(url)
        if "pre" in config:
            pre_op = config["pre"]
            pre_op = sorted(pre_op, key=lambda x: x["id"])
            for op in pre_op:
                if op["type"] == 0:
                    pass
                elif op["type"] == 1:
                    pass
                elif op["type"] == 2:
                    pass
        RETRY_COUNT = 1
        collection_count = len(collection)
        collection_point = 0
        while collection_point < collection_count:
            try:
                ret = {
                    'Date': datetime.datetime.now(),
                    'content': []
                }
                self.logger.info("Thread of " + url + " start collection : " + collection[collection_point]['name'])
                xpath = collection[collection_point]["xpath"]
                elem = self.browser.find_element(By.XPATH, xpath)
                if collection[collection_point]['type'] == 'class':
                    elem = elem.find_elements(By.CLASS_NAME, collection[collection_point]["child"])
                elif collection[collection_point]['type'] == 'tag':
                    elem = elem.find_elements(By.TAG_NAME, collection[collection_point]["child"])
                for e in elem:
                    ret['content'].append(e.text)
                self.result.append(ret)
                collection_point += 1
            except selenium.common.exceptions.StaleElementReferenceException as e:
                self.logger.warn(url + " has StaleElementReferenceException,retry in " + str(RETRY_COUNT))
                time.sleep(3)
                RETRY_COUNT += 1
                continue
            except selenium.common.exceptions.NoSuchElementException as e:
                self.logger.warn(url + " has no such element,retry in " + str(RETRY_COUNT))
                time.sleep(3)
                RETRY_COUNT += 1
                continue
            finally:
                if RETRY_COUNT == self.MAX_RETRY_COUNT:
                    self.logger.warn(url + f" has no such element,Retry in {RETRY_COUNT},Skip....")
                    collection_point += 1
                    RETRY_COUNT = 1
        self.logger.info("Thread of " + url + " has complete,Quit.")
