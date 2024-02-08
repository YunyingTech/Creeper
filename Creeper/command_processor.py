import base64
import json
import os.path

from Logger.Logger import Logger

# 创建一个日志记录器实例
logger = Logger()


class Processor:
    def process_command(self, data):
        if data["type"] == "file":
            self.process_file_command(data)
        elif data["type"] == "op":
            self.process_operation_command(data)
        else:
            self.process_default_command(data)

    def process_file_command(self, data):
        # 将base64解码后的内容写入文件
        with open(os.path.join("config", data["filename"]), "wb") as f:
            f.write(base64.b64decode(data['content']))
        # 记录文件已保存
        logger.info(f"{data['filename']} 已保存到配置目录")

    def process_operation_command(self, data):
        if data["op"] == "start":
            creeper_list = json.loads(data['content'])
            print(creeper_list)

    def process_default_command(self, command):
        # 打印命令
        print(command)
