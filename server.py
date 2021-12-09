from os import chdir, path, O_NONBLOCK, read, write, close
from subprocess import PIPE, Popen, call, check_output
from tempfile import NamedTemporaryFile
from workshop import getWorkshopItems
from time import sleep
from json import loads as json_loads
from requests import get as http_get
from utils import Timeout, get_default_ip, get_default_port
from a2s import info as a2s_info
from select import select
from threading import Thread
from sys import stdout
from pty import openpty
from fcntl import fcntl, F_GETFL, F_SETFL

STREAM_STDOUT = 0
STREAM_STDERR = 1

STATE_STOPPED = 0
STATE_STARTING = 1
STATE_RUNNING = 2
STATE_STOPPING = 3
STATE_LISTENING = 4
STATE_FAILING = 5

LOADADDONS_FILE_GMOD = "autorun/server/loadaddons.lua"
LOADADDONS_FILE_SERVER = "garrysmod/lua/%s" % LOADADDONS_FILE_GMOD

class ServerProcess:
    def __init__(self, folder, config):
        self.folder = path.abspath(folder)

        self.pidfile = path.join(self.folder, "pid")
        self.proc = None
        self.ptyMaster = None
        self.ptySlave = None
        self.stdoutThread = None

        self.config = config
        
        self.running = False
        self.state = STATE_STOPPED
        self.timeout = None
        
        self.ip = config.ip
        self.port = config.port

        if self.ip == "0.0.0.0":
            self.ip = get_default_ip()

        if self.port == 0:
            self.port = get_default_port()

        fh = open(path.join(self.folder, "garrysmod/sa_config/api.json"))
        data = fh.read()
        fh.close()

        dataDict = json_loads(data)
        self.serverToken = dataDict["serverToken"]
        self.apiAuth = "Server %s" % self.serverToken

    def getAPIData(self):
        res = http_get("https://api.spaceage.mp/v2/servers/self/config", headers={
            "Authorization": self.apiAuth,
        })
        return json_loads(res.text)

    def writeLocalConfig(self):
        self.switchTo()

        data = self.getAPIData()

        localCfg = """
sv_setsteamaccount %s
rcon_password "%s"
hostname "SpaceAge [%s]"
""" % (data["steam_account_token"], data["rcon_password"], data["name"])

        fh = open(path.join(self.folder, "garrysmod/cfg/localgame.cfg"), "w")
        fh.write(localCfg)
        fh.close()

        localCfg = """
require("sentry")
sentry.Setup("%s", {server_name = "%s"})
""" % (data["sentry_dsn"], data["name"])

        fh = open(path.join(self.folder, "garrysmod/lua/autorun/server/localcfg.lua"), "w")
        fh.write(localCfg)
        fh.close()

    def switchTo(self):
        chdir(self.folder)

    def updateBin(self):
        self.switchTo()

        steamcmdScript = """
@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
login anonymous
force_install_dir %s
app_update 4020 -beta x86-64
quit
""" % path.abspath(".")

        tmpFile = NamedTemporaryFile(mode="w+", suffix=".txt")

        tmpFile.write(steamcmdScript)
        tmpFile.flush()
        try:
            call(["steamcmd", "+runscript", tmpFile.name])
        finally:
            tmpFile.close()

    def updateWorkshopLua(self):
        self.switchTo()

        fileData = ""
        if self.config.workshop_clients:
            for item in getWorkshopItems(self.config.workshop_clients):
                fileData += "resource.AddWorkshop(\"%s\")\n" % item
        fh = open(LOADADDONS_FILE_SERVER, "w")
        fh.write(fileData)
        fh.close()

        self.exec("lua_openscript %s" % LOADADDONS_FILE_GMOD)

    def run(self):
        self.switchTo()

        if not path.exists(LOADADDONS_FILE_SERVER):
            self.updateWorkshopLua()

        args = ["./bin/linux64/srcds",
                    "-usercon", "-autoupdate", "-disableluarefresh", "-console",
                    "+ip", self.ip, "-port", "%i" % self.port,
                    "-tickrate", "%i" % self.config.tickrate, "-game", "garrysmod", "+maxplayers", "%i" % self.config.maxplayers,
                    "+map", self.config.map, "+gamemode", self.config.gamemode
        ]

        if self.config.workshop_server:
            args.append("+host_workshop_collection")
            args.append(self.config.workshop_server)

        env = {
            "LD_LIBRARY_PATH": path.abspath("./bin/linux64"),
        }

        self.kill()
        self.running = True
        self.setStateWithKillTimeout(STATE_STARTING, 60)

        self.ptyMaster, self.ptySlave = openpty()
        fl = fcntl(self.ptyMaster, F_GETFL)
        fcntl(self.ptyMaster, F_SETFL, fl | O_NONBLOCK)

        self.proc = Popen(args, env=env, bufsize=0, stdin=self.ptySlave, stdout=self.ptySlave, stderr=self.ptySlave, close_fds=True, encoding='utf-8')
        self.stdoutThread = Thread(target=self.stdoutThreadFunc, daemon=True, name="Server stdout")
        self.stdoutThread.start()
    
    def stdoutThreadFunc(self):
        ins = [self.ptyMaster]
        outs = []
        while self.running:
            readable, _, _ = select(ins, outs, ins)
            for fd in readable:
                data = read(fd, 8192).decode('utf-8')
                self.onOutput(data)

    def onOutput(self, data):
        stdout.write(data)
        stdout.flush()

    def setStateWithKillTimeout(self, state, timeout):
        if self.setState(state):
            self.setStateTimeout(timeout, self.kill)

    def setState(self, state):
        if self.state == state:
            return False
        self.clearStateTimeout()
        self.state = state
        print("[StarLord] Server state changed to %d" % self.state)
        return True

    def clearStateTimeout(self):
        if self.timeout:
            self.timeout.cancel()
            self.timeout = None

    def setStateTimeout(self, timeout, func):
        self.clearStateTimeout()
        self.timeout = Timeout(timeout, func)
        self.timeout.start()

    def restartIfEmpty(self):
        self.exec("restart_if_empty 1")

    def stop(self):
        if self.state == STATE_RUNNING:
            self.setStateWithKillTimeout(STATE_STOPPING, 15)
            self.exec("exit")
        elif self.state != STATE_STOPPING:
            self.kill()

    def kill(self):
        self.running = False
        self.setState(STATE_STOPPED)

        if self.proc:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
            self.proc = None

        if self.ptyMaster:
            close(self.ptyMaster)
            self.ptyMaster = None

        if self.ptySlave:
            close(self.ptySlave)
            self.ptySlave = None

    def exec(self, cmd):
        if not self.proc:
            return
        print("[StarLord] Running: %s" % cmd)
        write(self.ptyMaster, b"%s\n" % cmd.encode())

    def ping(self):
        addr = (self.ip, self.port)

        try:
            res = a2s_info(addr)
            if res.ping:
                return True
        except:
            pass
        
        return False

    def poll(self, waitTime):
        if not self.proc:
            return False

        sleep(waitTime)

        try:
            if self.proc.poll() != None:
                self.kill()
                return False
        except:
            return True

        if self.state == STATE_STARTING:
            lsof = ""
            try:
                lsof = check_output(["lsof", "-Pani", "-p", "%d" % self.proc.pid, "-FPn"]).decode("utf8").strip().split("\n")
            except:
                print("[StarLord] lsof failed...")
                pass

            serverUDP = False

            proto = None
            sock = None
            for line in lsof:
                typ = line[0]
                data = line[1:].strip()
                if typ == "P":
                    proto = data
                elif typ == "n":
                    sock = data

                if proto and sock:
                    if proto == "UDP" and sock == "%s:%d" % (self.ip, self.port):
                        serverUDP = True
                        break
                    proto = None
                    sock = None
            
            if serverUDP:
                self.setStateWithKillTimeout(STATE_LISTENING, 60)
        elif self.state == STATE_LISTENING:
            if self.ping():
                self.setState(STATE_RUNNING)
        elif self.state == STATE_RUNNING:
            if not self.ping():
                self.setStateWithKillTimeout(STATE_FAILING, 60)
        elif self.state == STATE_FAILING:
            if self.ping():
                self.setState(STATE_RUNNING)

        return True
