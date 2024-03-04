import os.path

import pymysql
import yaml


class MysqlConnector:
    host = "localhost"
    port = 3306
    username = "root"
    password = ""
    database = "creeper"
    connection = None
    cursor = None

    def __init__(self, database_config_file_path):
        if os.path.exists(database_config_file_path):
            database_config_file = open(database_config_file_path, "r")
            database_config_file_yaml = yaml.load(database_config_file.read(), Loader=yaml.FullLoader)
            self.host = database_config_file_yaml['mysql']['host']
            self.port = database_config_file_yaml['mysql']['port']
            self.username = database_config_file_yaml['mysql']['username']
            self.password = database_config_file_yaml['mysql']['password']
            self.database = database_config_file_yaml['mysql']['database']
            self.connection = pymysql.connect(host=self.host, port=self.port, user=self.username,
                                              password=self.password, database=self.database)
            self.cursor = self.connection.cursor()
        else:
            raise FileNotFoundError

    def write_to_creeper_log(self, log, client_id):
        if self.cursor is not None:
            self.connection.begin()
            self.cursor.execute(
                f"INSERT INTO osint.creeper_log (date, log, `from`) VALUES (DEFAULT, '{log}', {client_id});")
            self.connection.commit()
        else:
            raise ConnectionError("Mysql connect error")

    def write_to_config_list(self, file_name, url, collect_name):
        if self.cursor is not None:
            self.connection.begin()
            self.cursor.execute(
                f"INSERT INTO osint.creeper_config (file_name,url,collect_name) VALUES ('{file_name}','{url}','{collect_name}')")
            self.connection.commit()
        else:
            raise ConnectionError("Mysql connect error")

    def sql_query(self, sql_statement):
        if self.cursor is not None:
            self.cursor.execute(sql_statement)
            return self.cursor.fetchall()
        else:
            raise ConnectionError("Mysql connect error")

    def sql_delete(self, sql_statement, delete_item):
        if self.cursor is not None:
            self.cursor.execute(sql_statement, delete_item)  # delete_item格式为元组
            self.connection.commit()
        else:
            raise ConnectionError("Mysql connect error")

    def save_result(self,ret):
        """
        {date:xxx,content:[],url:xxx}
        """
        sql = "INSERT INTO raw_data(url,content,date) VALUES (%s,%s,%s)"
        self.cursor.execute(sql,[str(ret['url']),",".join(ret['content']),str(ret['Date'])])
        self.connection.commit()

    def __del__(self):
        self.connection.close()


if __name__ == "__main__":
    connector = MysqlConnector("./database.yaml")