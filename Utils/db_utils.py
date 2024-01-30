import datetime
import sqlite3


class DB:
    # 定义一个连接对象
    connection = None

    # 初始化函数，传入数据库路径
    def __init__(self, path):
        self.db_path = path
        # 连接数据库
        self.__connect()
        # 获取游标
        self.c = self.connection.cursor()
        # 定义默认表名
        self.DEFAULT_TABLE = "CONTENT"
        # 如果表不存在，则创建表
        if self.__exist_table():
            self.c.execute(
                f"CREATE TABLE IF NOT EXISTS {self.DEFAULT_TABLE} (id INTEGER PRIMARY KEY AUTOINCREMENT, date DATETIME, content varchar(4096))")

    # 判断表是否存在
    def __exist_table(self):
        # 执行SQL语句，查询sqlite_master表中类型为table，名字为DEFAULT_TABLE的记录
        self.c.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.DEFAULT_TABLE}'")
        # 获取查询结果
        result = self.c.fetchall()
        # 如果查询结果为空，则表不存在
        if result is None:
            return False
        # 如果查询结果不为空，则表存在
        else:
            return True

    def __connect(self):
        self.connection = sqlite3.connect(self.db_path)

    def save_result(self, data):
        """
        :param data:
        data = {
                    'Date': datetime.datetime.now(),
                    'content': []
                }
        :return: Boolean
        """
        date = data['Date'].strftime("%Y-%m-%d %H:%M:%S")
        print(date)
        contents = data["content"]
        for content in contents:
            self.c.execute(f"INSERT INTO {self.DEFAULT_TABLE} (date , content) values ('{date}' , '{content}')")
        self.connection.commit()



if __name__ == "__main__":
    # 创建一个DB对象，参数为db.sqlite3
    db = DB("db.sqlite3")
    # 调用save_result方法，参数为一个字典，包含当前时间和['Hello','World']
    db.save_result({'Date': datetime.datetime.now(), 'content': ['Hello',"World"]})