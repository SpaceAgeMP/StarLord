from os import unlink, getenv
from threading import Thread, Event
from socket import socket, AF_INET, SOCK_DGRAM

def get_default_ip():
    envip = getenv("SRCDS_IP")
    if envip:
        return envip
    addr = ("8.8.8.8", 53)
    s = socket(AF_INET, SOCK_DGRAM)
    s.connect(addr)
    ip = s.getsockname()[0]
    s.close()
    return ip

def get_default_port():
    envport = getenv("SRCDS_PORT")
    if envport:
        return int(envport)
    return 27015

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
        self.e = Event()

    def start(self):
        self.thread.start()

    def wait(self):
        self.thread.join()

    def cancel(self):
        self.running = False
        self.e.set()
    
    def _func(self):
        self.e.wait(timeout=self.timeout)
        if self.running:
            self.func()
