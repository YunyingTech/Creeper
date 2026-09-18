"""Optional MySQL storage, with parameterized writes and explicit connection lifetime."""

import os
from threading import RLock

from creeper_core.settings import read_yaml


class MysqlConnector:
    def __init__(self, database_config_file_path):
        try:
            import pymysql
        except ImportError as error:
            raise RuntimeError("Install requirements-mysql.txt to use MySQL") from error
        config = read_yaml(database_config_file_path).get("mysql", {})
        self._lock = RLock()
        self.connection = pymysql.connect(
            host=os.environ.get("CREEPER_MYSQL_HOST", config.get("host", "127.0.0.1")),
            port=int(os.environ.get("CREEPER_MYSQL_PORT", config.get("port", 3306))),
            user=os.environ.get("CREEPER_MYSQL_USER", config.get("username", "creeper")),
            password=os.environ.get("CREEPER_MYSQL_PASSWORD", config.get("password", "")),
            database=os.environ.get("CREEPER_MYSQL_DATABASE", config.get("database", "creeper")),
            charset="utf8mb4",
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )
        with self.connection.cursor() as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS raw_data (id BIGINT PRIMARY KEY AUTO_INCREMENT, "
                "url TEXT NOT NULL, content LONGTEXT NOT NULL, date VARCHAR(40) NOT NULL)"
            )
        self.connection.commit()

    def _write(self, statement, params):
        with self._lock:
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(statement, params)
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def write_to_creeper_log(self, log, client_id):
        self._write("INSERT INTO creeper_log (log, `from`) VALUES (%s, %s)", (log, client_id))

    def write_to_config_list(self, file_name, url, collect_name):
        self._write(
            "INSERT INTO creeper_config (file_name, url, collect_name) VALUES (%s, %s, %s)",
            (file_name, url, collect_name),
        )

    def sql_query(self, sql_statement, params=None):
        with self._lock, self.connection.cursor() as cursor:
            cursor.execute(sql_statement, params)
            return cursor.fetchall()

    def sql_delete(self, sql_statement, delete_item):
        self._write(sql_statement, delete_item)

    def save_result(self, ret):
        import json

        self._write(
            "INSERT INTO raw_data (url, content, date) VALUES (%s, %s, %s)",
            (ret["url"], json.dumps(ret["content"], ensure_ascii=False), ret["Date"].isoformat()),
        )
        return len(ret["content"])

    def close(self):
        self.connection.close()
