from git import GitRepo
from subprocess import check_call
from server import ServerProcess
from addon import Addon, isAddonUsed, isGamemodeUsed
from updateable import UpdateableResource
from luabin import makeLuaBin, isDLLUsed
from config import load
from os import listdir, path, getenv, waitpid, WNOHANG, unlink, mkfifo
from time import sleep
from threading import Thread, Event
from sys import stdin
from signal import SIGCHLD, SIGINT, SIGTERM, SIGHUP, SIGUSR1, SIGUSR2, signal
from timeutils import parse_timedelta
from traceback import print_exception
from typing import Any, cast, Callable

def handleSIGCHLD(_a: Any, _b: Any):
    _ = waitpid(-1, WNOHANG)
_ = signal(SIGCHLD, handleSIGCHLD)

enableSelfUpdate = getenv("ENABLE_SELF_UPDATE", "false") == "true"

SRCDS_CMD_FIFO = getenv("SRCDS_CMD_FIFO", "")
FOLDER = path.abspath(path.dirname(__file__))
selfRepo = GitRepo(FOLDER, "https://github.com/SpaceAgeMP/StarLord.git", "main")

config = load(cast(str, getenv("STARLORD_CONFIG")))

server = ServerProcess(path.join(cast(str, getenv("HOME")), "s"), config.server)
server.writeLocalConfig()

updateCheckerEvent = None
def fireUpdateChecker():
    global updateCheckerEvent
    if updateCheckerEvent:
        updateCheckerEvent.set()
        updateCheckerEvent = None

def handleSigusr1(_a: Any, _b: Any):
    fireUpdateChecker()
_ = signal(SIGUSR1, handleSigusr1)

def handleSigusr2(_a: Any, _b: Any):
    server.restartIfEmpty()
_ = signal(SIGUSR2, handleSigusr2)

def handleStopSignal(_a: Any, _b: Any):
    server.stop()
_ = signal(SIGTERM, handleStopSignal)
_ = signal(SIGINT, handleStopSignal)
_ = signal(SIGHUP, handleStopSignal)

addons: list[UpdateableResource] = []
for addonCfg in config.addons:
    addons.append(Addon(addonCfg))

for luaBinCfg in config.luabins:
    addons.append(makeLuaBin("garrysmod/lua/bin", luaBinCfg))

def runUpdates():
    server.updateBin()
    server.switchTo()
    for addon in addons:
        print("Updating", addon)
        try:
            addon.update()
        except Exception as e:
            print_exception(e)

def checkUpdates():
    hasUpdates = False
    if enableSelfUpdate:
        print("Checking self")
        try:
            hasUpdates = selfRepo.checkUpdate()
            if hasUpdates:
                print("Update found for self")
            selfRepo.update()
        except Exception as e:
            print_exception(e)
    else:
        print("Self update disabled")

    for addon in addons:
        print("Checking addon", addon)
        try:
            if addon.checkUpdate():
                print("Update found for addon", addon)
                hasUpdates = True
        except Exception as e:
            print_exception(e)

    print("Checking workshop")
    try:
        server.updateWorkshopLua()
    except Exception as e:
        print_exception(e)
    return hasUpdates

def cleanupFolder(folder: str, checkfn: Callable[[str], bool]):
    if not path.exists(folder):
        return

    _ = check_call(["rm", "-rf"] + [path.join(folder, file) for file in listdir(folder) if not checkfn(file)])

def cleanupFolders():
    server.switchTo()
    cleanupFolder("garrysmod/gamemodes", isGamemodeUsed)
    cleanupFolder("garrysmod/addons", isAddonUsed)
    cleanupFolder("garrysmod/lua/bin", isDLLUsed)

runUpdates()
cleanupFolders()
server.run()

def updateChecker():
    global updateCheckerEvent
    while server.running:
        print("Checking for updates...")
        try:
            hasUpdates = checkUpdates()
            if hasUpdates:
                server.restartIfEmpty()
        except Exception as e:
            print("Error checking for updates")
            print_exception(e)

        updateCheckerEvent = Event()
        _ = updateCheckerEvent.wait(timeout=600)

def stdinChecker():
    for line in stdin:
        server.exec(line.strip())

def fifoReader():
    while True:
        with open(SRCDS_CMD_FIFO) as fifo:
            for line in fifo:
                server.exec(line.strip())

def restartTimer():
    if not config.server.restart_every:
        return
    timedelta = parse_timedelta(config.server.restart_every)
    sleep(timedelta.total_seconds())
    server.restartIfEmpty()

updateCheckerThread = Thread(target=updateChecker, name="Update checker")
updateCheckerThread.start()

restartTimerThread = Thread(target=restartTimer, name="Restart timer", daemon=True)
restartTimerThread.start()

if stdin.isatty():
    stdinThread = Thread(target=stdinChecker, name="STDIN reader", daemon=True)
    stdinThread.start()

if SRCDS_CMD_FIFO:
    try:
        unlink(SRCDS_CMD_FIFO)
    except:
        pass
    mkfifo(SRCDS_CMD_FIFO)
    fifoThread = Thread(target=fifoReader, name="FIFO reader", daemon=True)
    fifoThread.start()

while server.poll(waitTime=1):
    pass

fireUpdateChecker()
updateCheckerThread.join()
