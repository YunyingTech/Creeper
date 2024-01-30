import base64
import json
import os.path

from Logger.Logger import Logger

# 创建一个日志记录器实例
logger = Logger()


def process(command):
    data = command
    if data["type"] == "file":
       # 将base64解码后的内容写入文件
       with open(os.path.join("config", data["filename"]), "wb") as f:
           f.write(base64.b64decode(data['content']))
       # 记录文件已保存
       logger.info(f"{data['filename']} 已保存到配置目录")
    elif data["type"] == "op":
        pass
    else:
       # 打印命令
       print(command)


class Processor:
    def __int__(self):
        # 调用父类构造函数
        pass
