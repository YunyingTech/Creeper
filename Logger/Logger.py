import datetime
import os


class Logger:
    # 初始化函数，设置日志文件路径
    def __init__(self):
        self.logger_file_path = "./"
        self.logger_file = open(os.path.join(self.logger_file_path, "creeper.log"), "a", encoding="utf8")

    # 打印信息
    def info(self, log):
        log_str = "[%s INFO    ] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log)
        self.logger_file.write(log_str + "\n")
        print("[%s INFO    ] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log))

    # 打印警告
    def warn(self, log):
        log_str = "[%s WARNING ] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log)
        self.logger_file.write(log_str + "\n")
        print("\033[0;33m[%s WARNING ] %s\033[0m" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log))

    # 打印错误
    def error(self, log):
        log_str = "[%s ERROR   ] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log) + "\n"
        self.logger_file.write(log_str + "\n")
        print("\033[0;31m[%s ERROR   ] %s\033[0m" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log))

    # 打印严重错误
    def critical(self, log):
        log_str = "[%s CRITICAL] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log)
        self.logger_file.write(log_str + "\n")
        print("\033[0;31m[%s CRITICAL] %s\033[0m" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), log))

    # 关闭日志文件
    def __del__(self):
        self.logger_file.close()


if __name__ == "__main__":
    # 实例化日志类
    logger = Logger()
    # 打印信息
    logger.info("Starting")
    # 打印警告
    logger.warn("Starting")
    # 打印错误
    logger.error("Starting")