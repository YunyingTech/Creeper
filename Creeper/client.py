import socket
import threading
import time
import json

from Creeper.command_processor import Processor
from Logger.Logger import Logger
from Utils.send_encode import send_encode

logger = Logger()


class Client:
    def __init__(self, IP, PORT):
        self.IP = IP
        self.PORT = PORT
        self.MAX_RETRY_COUNT = 3
        self.client_socket = None
        self.server_living = False
        self.processor = Processor()

    def connect_to_server(self):
        retry_count = 0
        while retry_count <= self.MAX_RETRY_COUNT:
            try:
                self.client_socket = socket.socket()
                self.client_socket.connect((self.IP, self.PORT))
                logger.info("Connected to the server successfully.")
                self.server_living = True
                self.start_heartbeat_thread()
                self.start_receive_command_thread()
                return True
            except TimeoutError:
                retry_count += 1
                logger.warn(f"Connection timed out, retrying. Retries: {retry_count}")
        logger.error("Connection to server failed, please check the link")
        return False

    def start_heartbeat_thread(self):
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()

    def send_heartbeat(self):
        heartbeat_commands = {
            "type": "HB",
            "content": "HB"
        }
        while self.server_living:
            try:
                self.client_socket.send(send_encode(heartbeat_commands))
                time.sleep(75)
            except ConnectionResetError:
                self.handle_connection_lost()
            except OSError:
                logger.warn("Connection lost.Retry")

    def start_receive_command_thread(self):
        receive_command_thread = threading.Thread(target=self.receive_command, daemon=True)
        receive_command_thread.start()
        receive_command_thread.join()

    def receive_command(self):
        heartbeat_commands = {
            "type": "HB",
            "content": "HC"
        }
        while self.server_living:
            try:
                datas = self.client_socket.recv(1024).decode('utf8').strip()
                for data in datas.split("\r\n"):
                    try:
                        data = json.loads(data)
                        if data['content'] == "HB":
                            self.server_living = True
                        elif data['content'] == "HC":
                            self.client_socket.send(send_encode(heartbeat_commands))
                        else:
                            self.processor.process_command(data)
                    except json.decoder.JSONDecodeError:
                        logger.warn(f"Json parser warning, command is {data}")
            except ConnectionResetError:
                self.handle_connection_lost()

    def handle_connection_lost(self):
        logger.warn("Connection lost.Retry")
        self.client_socket.close()
        self.server_living = False
        self.reconnect_to_server()

    def reconnect_to_server(self):
        while not self.server_living:
            try:
                time.sleep(5)
                if self.connect_to_server():
                    break
                logger.warn("Connection lost.Retry")
            except ConnectionRefusedError:
                continue

    def close_socket(self):
        if self.client_socket:
            self.client_socket.close()
