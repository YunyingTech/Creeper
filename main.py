import time

import Banner
from Creeper.client import Client
from Creeper.daemon import Daemon
from Creeper.server import Server
from Logger.Logger import Logger
import yaml
import argparse

__version__ = "1.0.2"

Banner.banner()
logger = Logger()
logger.info(f"Starting Creeper Version {__version__}")

if __name__ == "__main__":
    # 创建一个参数解析器，用于解析参数
    parser = argparse.ArgumentParser(description='Creeper args parser')
    # 添加参数，参数类型为字符串，默认值为single，参数名称为mode，用于选择运行模式，可选值为server,client or single
    parser.add_argument('--mode', type=str, default="single", metavar="server,client or single", help="Choose the "
                                                                                                      "mode to run "
                                                                                                      "the system")
    # 解析参数
    args = parser.parse_args()
    try:
        # 加载配置文件
        config = yaml.load(open("config.yaml", "r"), Loader=yaml.FullLoader)
        logger.info("Configuration file loaded successfully")
        # 判断运行模式
        if args.mode == "client":
            # 从配置文件中获取服务器IP和端口号
            server_ip = config["server-ip"]
            server_port = config["server-port"]
            logger.info(f"Creeper system running in client mode")
            logger.info(f"Detected server and port number in the configuration file as {server_ip}:{server_port}")
            # 创建客户端实例
            client = Client(server_ip, server_port)
            # 连接到服务器
            client.connect_to_server()
        elif args.mode == "server":
            logger.info(f"Creeper system running in server mode")
            # 创建服务器实例，并设置最大连接数
            server = Server(config["listen-port"], max_connection=config["max_connection"])
            # 启动服务器socket
            server.start_server_socket()
        elif args.mode == "single":
            # 创建守护进程实例
            daemon = Daemon()
            # 检测设备
            daemon.detect()
            # 运行爬虫
            daemon.creeper()
        else:
            logger.error(
                "Running mode error, can only be selected from the following three modes: server client single")

    except FileNotFoundError as e:
        logger.critical("Config file not found,please check it.")