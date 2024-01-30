import base64
import os
import socket
import threading
import time
import json

from Logger.Logger import Logger
from Utils.send_encode import send_encode

logger = Logger()


# 定义一个函数，用于发送心跳包，参数为客户端套接字
def send_heart_beat(client_socket):
    # 创建一个字典，用于存储发送的心跳包内容
    commands = {
        "type": "HB",
        "content": "HB"
    }
    try:
        # 循环发送心跳包，每隔75秒发送一次
        while True:
            # 使用send_encode函数对字典进行编码，并发送
            client_socket.send(send_encode(commands))
            # 每次发送后等待75秒
            time.sleep(75)
    # 如果发送失败，捕获异常，并返回False
    except ConnectionResetError as e:
        return False


class Server:
    def __init__(self, PORT, max_connection):
        # 初始化端口号和最大连接数
        self.PORT = PORT
        self.max_connection = max_connection
        # 初始化tcp服务器套接字
        self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 设置套接字参数，使服务器可以重用地址
        self.tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        # 绑定服务器和端口号
        self.tcp_server_socket.bind(("", self.PORT))
        # 设置最大连接数
        self.tcp_server_socket.listen(self.max_connection)

        # 初始化客户端连接数
        self.connection_count = 0
        # 初始化活跃的客户端
        self.living_client = {}

    def start_server_socket(self):
        logger.info(f"Start listening in {self.PORT},max connection is {self.max_connection}")

        while True:
            # 接受客户端连接
            client, IP_PORT = self.tcp_server_socket.accept()
            # 创建子线程处理客户端请求
            sub_thread = threading.Thread(target=self.handle_client_request,
                                          args=(IP_PORT, client, self.max_connection,),
                                          daemon=True)
            sub_thread.start()
            # 创建子线程发送心跳包
            heart_beat_th = threading.Thread(target=send_heart_beat, args=(client,), daemon=True)
            heart_beat_th.start()

            # 等待3秒
            time.sleep(3)
            # 向客户端发送命令
            self.send_command("Transfer File")

# 定义一个处理客户端请求的函数，参数为IP_PORT，client_socket，max_connection
    def handle_client_request(self, IP_PORT, client_socket, max_connection):
        # 定义一个变量，用于记录节点存活时间
        living_time = 0

        # 定义一个字典，用于发送心跳包
        heart_beat_commands = {
            "type": "HB",
            "content": "HB"
        }
        try:
            # 连接数加一
            self.connection_count += 1
            # 打印节点连接信息
            logger.info(f"New NODE find in {IP_PORT},connected [{self.connection_count}/{max_connection}]")
            # 循环接收客户端发送的数据
            while client_socket:
                # 接收客户端发送的数据
                datas = client_socket.recv(1024).decode("utf8").strip()
                # 遍历接收到的数据
                for data in datas.split("\r\n"):
                    try:
                        # 将接收到的数据转换为字典
                        data = json.loads(data)
                        # 如果接收到的数据为心跳包
                        if data['content'] == "HB":
                            # 节点存活时间加75
                            living_time += 75
                            # 将节点信息更新到living_client中
                            self.living_client.update({f"{IP_PORT[0]}:{IP_PORT[1]}": [living_time, client_socket]})
                            # 向客户端发送心跳包
                            client_socket.send(send_encode(heart_beat_commands))
                    # 如果接收到的数据不是心跳包，则抛出异常
                    except json.decoder.JSONDecodeError as e:
                        logger.warn(f"Json parser warning,command is {data}")
        # 如果客户端断开连接，则连接数减一
        except ConnectionResetError as e:
            self.connection_count -= 1
            logger.info(f"NODE {IP_PORT},disconnected [{self.connection_count}/{max_connection}]")
            # 从living_client中删除断开连接的节点
            self.living_client.pop(f"{IP_PORT[0]}:{IP_PORT[1]}")

# 定义一个函数，用于发送命令
    def send_command(self, command):
# 如果命令是“Start creeper”，则打印日志信息，并发送命令到所有节点
        if command == "Start creeper":
            logger.info("Send 'Start creeper' to all node")
            commands = {
                "type": "op",
                "content": command
            }
            for i in self.living_client:
                self.living_client[i][1].sendall(send_encode(commands))
# 如果命令是“Transfer File”，则打印日志信息，并发送文件列表到所有节点
        elif command == "Transfer File":
            logger.info("Send 'Transfer File' to all node")
            filelist = os.listdir('ServerConfig')
            for file in filelist:
                commands = {
                    "type": "file",
                    "filename": file,
                    "content": base64.b64encode(open(os.path.join('ServerConfig', file), "rb").read()).decode('utf8')
                }
                for i in self.living_client:
                    self.living_client[i][1].sendall(send_encode(commands))
# 否则，将命令发送到所有节点
        else:
            commands = {
                "type": "other",
                "content": command
            }
            for i in self.living_client:
                self.living_client[i][1].sendall(json.dumps(commands).encode("utf8"))