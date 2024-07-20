from os import chdir, path, O_NONBLOCK, read, write, close, getenv, makedirs
from subprocess import Popen, check_call, check_output
from tempfile import NamedTemporaryFile
from traceback import print_exc
from workshop import getWorkshopItems
from time import sleep
from json import loads as json_loads, dumps as json_dumps
from requests import get as http_get
from utils import Timeout, get_default_ip, get_default_port
from a2s import info as a2s_info # type: ignore
from select import select
from threading import Thread
from sys import stdout
from pty import openpty
from fcntl import fcntl, F_GETFL, F_SETFL
from config import ServerConfig
from typing import cast, Callable, Any

STREAM_STDOUT = 0
STREAM_STDERR = 1

STATE_STOPPED = 0
STATE_STARTING_PRE_WORKSHOP = 1
STATE_STARTING_IN_WORKSHOP = 2
STATE_STARTING_POST_WORKSHOP = 3
STATE_RUNNING = 4
STATE_STOPPING = 5
STATE_LISTENING = 6
STATE_FAILING = 7

LOADADDONS_FILE_GMOD = "autorun/server/loadaddons.lua"
LOADADDONS_FILE_SERVER = "garrysmod/lua/%s" % LOADADDONS_FILE_GMOD

LD_LIBRARY_PATHS = ["./linux64", "./bin/linux64"]

class ServerProcess:
    folder: str
    pidfile: str
    ip: str

    def __init__(self, folder: str, config: ServerConfig):
        super().__init__()
        self.folder = path.abspath(folder)
        makedirs(self.folder, exist_ok=True)

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

        apiJsonFile = path.join(self.folder, "garrysmod/data_static/sa_config/api.json")
        self.serverToken = getenv("SPACEAGE_SERVER_TOKEN")
        self.apiAuth = "Server %s" % self.serverToken

        apiJsonData = {}
        if path.exists(apiJsonFile):
            with open(apiJsonFile, "r") as fh:
                apiJsonData = cast(dict[str, Any], json_loads(fh.read()))

        if apiJsonData.get("serverToken", "") != self.serverToken:
            apiJsonData["serverToken"] = self.serverToken
            makedirs(path.dirname(apiJsonFile), exist_ok=True)
            with open(apiJsonFile, "w") as fh:
                _ = fh.write(json_dumps(apiJsonData))

    def getAPIData(self):
        res = http_get("https://api.spaceage.mp/v2/servers/self/config", headers={
            "Authorization": self.apiAuth,
        })
        res.raise_for_status()
        return json_loads(res.text)

    def writeLocalConfig(self):
        self.switchTo()

        data = self.getAPIData()

        localCfg = """
sv_setsteamaccount %s
rcon_password "%s"
hostname "SpaceAge [%s]"
""" % (data["steam_account_token"], data["rcon_password"], data["name"])

        makedirs(path.join(self.folder, "garrysmod/cfg"), exist_ok=True)
        fh = open(path.join(self.folder, "garrysmod/cfg/localgame.cfg"), "w")
        _ = fh.write(localCfg)
        fh.close()

        localCfg = """
require("sentry")
sentry.Setup("%s", {server_name = "%s"})
""" % (data["sentry_dsn"], data["name"])

        makedirs(path.join(self.folder, "garrysmod/lua/autorun/server"), exist_ok=True)
        fh = open(path.join(self.folder, "garrysmod/lua/autorun/server/localcfg.lua"), "w")
        _ = fh.write(localCfg)
        fh.close()

    def switchTo(self):
        chdir(self.folder)

    def updateBin(self):
        self.switchTo()

        steamcmdScript = """
@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
force_install_dir %s
login anonymous
app_update 4020 -beta x86-64
quit
""" % path.abspath(".")

        tmpFile = NamedTemporaryFile(mode="w+", suffix=".txt")

        _ = tmpFile.write(steamcmdScript)
        tmpFile.flush()
        try:
            _ = check_call(["steamcmd", "+runscript", tmpFile.name])
        finally:
            tmpFile.close()

    def updateWorkshopLua(self):
        self.switchTo()

        fileData = ""
        if self.config.workshop_clients:
            for item in getWorkshopItems(self.config.workshop_clients):
                fileData += "resource.AddWorkshop(\"%s\")\n" % item
        fh = open(LOADADDONS_FILE_SERVER, "w")
        _ = fh.write(fileData)
        fh.close()

        self.exec("lua_openscript %s" % LOADADDONS_FILE_GMOD)

    def run(self):
        self.switchTo()

        if not path.exists(LOADADDONS_FILE_SERVER):
            self.updateWorkshopLua()

        args: list[str] = ["./bin/linux64/srcds",
                    "-usercon", "-autoupdate", "-disableluarefresh", "-console", "-allowlocalhttp",
                    "+ip", self.ip, "-port", "%i" % self.port,
                    "-tickrate", "%i" % self.config.tickrate, "-game", "garrysmod", "+maxplayers", "%i" % self.config.maxplayers,
                    "+map", self.config.map, "+gamemode", self.config.gamemode
        ]

        if self.config.workshop_server:
            args.append("+host_workshop_collection")
            args.append(self.config.workshop_server)

        env: dict[str, str] = {
            "LD_LIBRARY_PATH": ":".join([path.abspath(p) for p in LD_LIBRARY_PATHS]),
            "HOME": cast(str, getenv("HOME")),
        }

        self.kill()
        self.running = True
        self.setStateWithKillTimeout(STATE_STARTING_PRE_WORKSHOP, 60)

        self.ptyMaster, self.ptySlave = openpty()
        fl = fcntl(self.ptyMaster, F_GETFL)
        _ = fcntl(self.ptyMaster, F_SETFL, fl | O_NONBLOCK)

        self.proc = Popen(args, env=env, bufsize=0, stdin=self.ptySlave, stdout=self.ptySlave, stderr=self.ptySlave, close_fds=True, encoding='utf-8')
        self.stdoutThread = Thread(target=self.stdoutThreadFunc, daemon=True, name="Server stdout")
        self.stdoutThread.start()
    
    def stdoutThreadFunc(self):
        while self.running:
            ins = [self.ptyMaster]
            readable, _, _ = select(ins, [], ins)
            for fd in readable:
                try:
                    data = read(fd, 8192).decode('utf-8')
                    self.onOutput(data)
                except:
                    print("[StarLord] Process state:", self.proc)
                    print_exc()

    def onOutput(self, data: str):
        _ = stdout.write(data)
        _ = stdout.flush()

        if self.state == STATE_STARTING_PRE_WORKSHOP:
            if "WS: Processing " in data:
                self.setStateWithKillTimeout(STATE_STARTING_IN_WORKSHOP, 60)
        elif self.state == STATE_STARTING_IN_WORKSHOP:
            if "Addon needs downloading..." in data:
                self.reconfigureStateKillTimeout(600)
                print("[StarLord] Kill timeout set to 600 seconds due to workshop download start", flush=True)
            elif "Mounted!" in data:
                self.reconfigureStateKillTimeout(60)
                print("[StarLord] Kill timeout set to 60 seconds due to workshop download end", flush=True)
            elif "WS: Finished!" in data:
                self.setStateWithKillTimeout(STATE_STARTING_POST_WORKSHOP, 60)

    def setStateWithKillTimeout(self, state: int, timeout: float):
        if self.setState(state):
            self.reconfigureStateKillTimeout(timeout)

    def reconfigureStateKillTimeout(self, timeout: float):
        self.setStateTimeout(timeout, self.kill)

    def setState(self, state: int):
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

    def setStateTimeout(self, timeout: float, func: Callable[[], None]):
        self.clearStateTimeout()
        self.timeout = Timeout(timeout, func)
        self.timeout.start()

    def restartIfEmpty(self):
        self.exec("restart_if_empty 1")

    def stop(self):
        print("[StarLord] Stop server")
        if self.state == STATE_RUNNING:
            self.setStateWithKillTimeout(STATE_STOPPING, 15)
            self.exec("exit")
        elif self.state != STATE_STOPPING:
            self.kill()

    def kill(self):
        print("[StarLord] Kill server")
        self.running = False
        _ = self.setState(STATE_STOPPED)

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

        if self.stdoutThread:
            self.stdoutThread.join()
            self.stdoutThread = None

    def exec(self, cmd: str):
        if not self.proc:
            return
        print("[StarLord] Running: %s" % cmd)
        _ = write(cast(int, self.ptyMaster), b"%s\n" % cmd.encode())

    def ping(self):
        addr = (self.ip, self.port)

        try:
            res = a2s_info(addr) # type: ignore
            if res.ping: # type: ignore
                return True
        except:
            pass
        
        return False

    def poll(self, waitTime: float):
        if not self.proc:
            return False

        sleep(waitTime)

        try:
            if self.proc.poll() != None:
                self.kill()
                return False
        except:
            return True

        if self.state == STATE_STARTING_PRE_WORKSHOP or self.state == STATE_STARTING_IN_WORKSHOP or self.state == STATE_STARTING_POST_WORKSHOP:
            if self.ping():
                self.setStateWithKillTimeout(STATE_LISTENING, 60)
        elif self.state == STATE_LISTENING:
            if self.ping():
                _ = self.setState(STATE_RUNNING)
        elif self.state == STATE_RUNNING:
            if not self.ping():
                self.setStateWithKillTimeout(STATE_FAILING, 60)
        elif self.state == STATE_FAILING:
            if self.ping():
                _ = self.setState(STATE_RUNNING)

        return True
