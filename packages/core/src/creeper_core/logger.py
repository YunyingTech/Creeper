"""Thread-safe shared logging with bounded log files."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

_lock = Lock()


class Logger:
    def __init__(self):
        self.logger = logging.getLogger("creeper")
        with _lock:
            if not self.logger.handlers:
                self.logger.setLevel(logging.INFO)
                self.logger.propagate = False
                formatter = logging.Formatter("[%(asctime)s %(levelname)-8s] %(message)s")
                console = logging.StreamHandler()
                console.setFormatter(formatter)
                self.logger.addHandler(console)
                path = Path.cwd() / "data" / "creeper.log"
                path.parent.mkdir(parents=True, exist_ok=True)
                handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

    def info(self, log):
        self.logger.info(log)

    def warn(self, log):
        self.logger.warning(log)

    warning = warn

    def error(self, log):
        self.logger.error(log)

    def critical(self, log):
        self.logger.critical(log)
