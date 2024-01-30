import socket
import threading
import time
import json

from Creeper.client_commands import process
from Logger.Logger import Logger
from Utils.send_encode import send_encode

logger = Logger()


# 定义发送心跳函数
def send_heart_beat(client_socket):
    # 创建心跳命令字典
    heart_beat_commands = {
        "type": "HB",
        "content": "HB"
    }
    try:
        # 循环发送心跳命令
        while True:
            # 编码发送心跳命令
            client_socket.client_socket.send(send_encode(heart_beat_commands))
            # 每75秒发送一次心跳命令
            time.sleep(75)
    # 捕获连接中断错误
    except ConnectionResetError as e:
        # 设置服务器连接状态为False
        client_socket.server_living = False
    # 捕获连接拒绝错误
    except ConnectionRefusedError as e:
        # 设置服务器连接状态为False
        client_socket.server_living = False
    # 捕获其他错误
    except OSError as e:
        # 记录警告信息
        logger.warn(f"Connection lost.Retry")


# 定义接收命令函数，接收客户端套接字
def recv_command(client_socket):
    # 定义心跳命令
    heart_beat_commands = {
        "type": "HB",
        "content": "HC"
    }
    try:
        # 循环接收命令
        while True:
            # 接收客户端套接字发送的数据，并解码
            datas = client_socket.client_socket.recv(1024).decode('utf8').strip()
            # 将接收到的数据按换行符分割
            for data in datas.split("\r\n"):
                try:
                    # 将数据转换为json格式
                    data = json.loads(data)
                    # 如果数据内容为心跳命令，则设置客户端在线状态为True
                    if data['content'] == "HB":
                        client_socket.server_living = True
                    # 如果数据内容为心跳命令，则发送心跳命令
                    elif data['content'] == "HC":
                        client_socket.client_socket.send(send_encode(heart_beat_commands))
                    # 否则，调用处理函数处理数据
                    else:
                        process(data)
                # 如果转换为json格式失败，则打印警告信息
                except json.decoder.JSONDecodeError as e:
                    logger.warn(f"Json parser warning,command is {data}")
    # 如果接收命令时，客户端套接字被重置，则打印警告信息，关闭客户端套接字，重新连接服务器
    except ConnectionResetError as e:
        logger.warn(f"Connection lost.Retry")
        client_socket.client_socket.close()
        while True:
            try:
                # 等待5秒，重新连接服务器
                time.sleep(5)
                if client_socket.connect_to_server():
                    break
                logger.warn(f"Connection lost.Retry")
            # 如果连接服务器时，服务器拒绝连接，则继续重试连接
            except ConnectionRefusedError as e:
                continue
    # 如果接收命令时，客户端套接字被拒绝，则打印警告信息，关闭客户端套接字，重新连接服务器
    except ConnectionRefusedError as e:
        logger.warn(f"Connection lost.Retry")
        client_socket.client_socket.close()
        while True:
            try:
                # 等待5秒，重新连接服务器
                time.sleep(5)
                if client_socket.connect_to_server():
                    break
                logger.warn(f"Connection lost.Retry")
            # 如果连接服务器时，服务器拒绝连接，则继续重试连接
            except ConnectionRefusedError as e:
                continue

# 定义一个Client类，用于连接服务器
class Client:
    # 初始化函数，设置服务器IP和端口号
    def __init__(self, IP, PORT):
        self.IP = IP
        self.PORT = PORT
        # 设置最大重试次数
        self.MAX_RETRY_COUNT = 3
        # 创建socket对象
        self.client_socket = socket.socket()
        # 设置服务器连接状态
        self.server_living = False

    # 连接服务器函数，重试次数超过最大重试次数则返回False
    def connect_to_server(self):
        RETRY_COUNT = 0
        while RETRY_COUNT <= self.MAX_RETRY_COUNT:
            try:
                # 连接服务器
                self.client_socket = socket.socket()
                self.client_socket.connect((self.IP, self.PORT))
                logger.info("Connected to the server successfully.")
                # 设置服务器连接状态为True
                self.server_living = True
                break
            except TimeoutError as e:
                RETRY_COUNT += 1
                logger.warn(f"Connection timed out, retrying. Retries: {RETRY_COUNT}")
            finally:
                if RETRY_COUNT > self.MAX_RETRY_COUNT:
                    logger.error("Connection to server failed, please check the link")
                    return False
        # 创建心跳线程和接收命令线程
        heart_beat_th = threading.Thread(target=send_heart_beat, args=(self,), daemon=False)
        recv_command_th = threading.Thread(target=recv_command, args=(self,), daemon=False)
        # 启动线程
        heart_beat_th.start()
        recv_command_th.start()
        return True

    # 关闭socket对象
    def __int__(self):
        self.client_socket.close()