import json


def send_encode(command):
    return (json.dumps(command) + "\r\n").encode('utf8')
