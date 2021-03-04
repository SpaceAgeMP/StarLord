from os import unlink
from threading import Thread
from time import sleep
from socket import socket, AF_INET, SOCK_DGRAM

def get_default_ip():
    addr = ("8.8.8.8", 53)
    s = socket(AF_INET, SOCK_DGRAM)
    s.connect(addr)
    ip = s.getsockname()[0]
    s.close()
    return ip

def unlink_safe(path):
    try:
        unlink(path)
        return True
    except:
        return False

class Timeout:
    def __init__(self, timeout, func):
        self.timeout = timeout
        self.func = func
        self.running = True
        self.thread = Thread(target=self._func, daemon=True)

    def start(self):
        self.thread.start()

    def wait(self):
        self.thread.join()

    def cancel(self):
        self.running = False
    
    def _func(self):
        sleep(self.timeout)
        if self.running:
            self.func()
