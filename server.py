from os import chdir, path
from subprocess import PIPE, Popen, call, check_output
from tempfile import NamedTemporaryFile
from workshop import getWorkshopItems
from time import sleep
from json import loads as json_loads
from requests import get as http_get
from utils import Timeout

STREAM_STDOUT = 0
STREAM_STDERR = 1

STATE_STOPPED = 0
STATE_STARTING = 1
STATE_RUNNING = 2
STATE_STOPPING = 3

LOADADDONS_FILE_GMOD = "autorun/server/loadaddons.lua"
LOADADDONS_FILE_SERVER = "garrysmod/lua/%s" % LOADADDONS_FILE_GMOD

class ServerProcess:
    def __init__(self, folder, config):
        self.folder = path.abspath(folder)

        self.pidfile = path.join(self.folder, "pid")
        self.proc = None

        self.config = config
        
        self.running = False
        self.state = STATE_STOPPED
        self.timeout = None

        fh = open(path.join(self.folder, "garrysmod/sa_config/api.json"))
        data = fh.read()
        fh.close()

        dataDict = json_loads(data)
        self.serverToken = dataDict["serverToken"]
        self.apiAuth = "Server %s" % self.serverToken

    def getAPIData(self):
        res = http_get("https://api.spaceage.mp/v2/servers/self", headers={
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
                    "-tickrate", "%i" % self.config.tickrate, "-game", "garrysmod", "+ip", self.config.ip, "+maxplayers", "%i" % self.config.maxplayers,
                    "+map", self.config.map, "+gamemode", self.config.gamemode
        ]

        if self.config.workshop_server:
            args.append("+host_workshop_collection")
            args.append(self.config.workshop_server)

        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/game",
            "LD_LIBRARY_PATH": path.abspath("./bin/linux64"),
        }

        self.kill()
        self.running = True
        self.setState(STATE_STARTING)
        self.proc = Popen(args, env=env, stdin=PIPE, close_fds=True, encoding='utf-8')
        self.setStateTimeout(60, self.kill)

    def setState(self, state):
        self.clearStateTimeout()
        self.state = state
        print("[StarLord] Server state changed to %d" % self.state)

    def clearStateTimeout(self):
        if self.timeout:
            self.timeout.cancel()
            self.timeout = None

    def setStateTimeout(self, timeout, func):
        self.clearStateTimeout()
        self.timeout = Timeout(timeout, func)
        self.timeout.start()

    def stop(self):
        if self.state == STATE_RUNNING:
            self.setState(STATE_STOPPING)
            self.exec("exit")
            self.setStateTimeout(15, self.kill)
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
            
    def exec(self, cmd):
        if not self.proc:
            return
        print("[StarLord] Running: %s" % cmd)
        self.proc.stdin.write("%s\n" % cmd)
        self.proc.stdin.flush()

    def poll(self, waitTime):
        if not self.proc:
            return False
        sleep(waitTime)
        if self.proc.poll() != None:
            self.kill()
            return False

        if self.state == STATE_STARTING:
            lsof = check_output(["lsof", "-Pani", "-p", "%d" % self.proc.pid, "-FPn"]).decode("utf8").strip().split("\n")

            clistenUDP = 0

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
                    if proto == "UDP" and sock[0:2] == "*:":
                        clistenUDP += 1
                    proto = None
                    sock = None
            
            if clistenUDP >= 3:
                self.setState(STATE_RUNNING)

        return True
