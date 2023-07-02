from git import GitRepo
from subprocess import check_call
from server import ServerProcess
from addon import Addon, isAddonUsed, isGamemodeUsed
from luabin import makeLuaBin, isDLLUsed
from config import load
from os import listdir, path, getenv, waitpid, WNOHANG
from time import sleep
from threading import Thread, Event
from sys import stdin
from signal import SIGCHLD, SIGINT, SIGTERM, SIGHUP, SIGUSR1, SIGUSR2, signal
from timeutils import parse_timedelta
from traceback import print_exception

def handleSIGCHLD(_a, _b):
    waitpid(-1, WNOHANG)
signal(SIGCHLD, handleSIGCHLD)

FOLDER = path.abspath(path.dirname(__file__))
selfRepo = GitRepo(FOLDER, "https://github.com/SpaceAgeMP/StarLord.git", "main")

config = load(getenv("STARLORD_CONFIG"))

server = ServerProcess(path.join(getenv("HOME"), "s"), config.server)
server.writeLocalConfig()

updateCheckerEvent = None
def fireUpdateChecker():
    global updateCheckerEvent
    if updateCheckerEvent:
        updateCheckerEvent.set()
        updateCheckerEvent = None

def handleSigusr1(_a, _b):
    fireUpdateChecker()
signal(SIGUSR1, handleSigusr1)

def handleSigusr2(_a, _b):
    server.restartIfEmpty()
signal(SIGUSR2, handleSigusr2)

def handleStopSignal(_a, _b):
    server.stop()
signal(SIGTERM, handleStopSignal)
signal(SIGINT, handleStopSignal)
signal(SIGHUP, handleStopSignal)

addons = []
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
    print("Checking self")
    try:
        hasUpdates = selfRepo.checkUpdate()
        if hasUpdates:
            print("Update found for self")
        selfRepo.update()
    except Exception as e:
        print_exception(e)

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

def cleanupFolder(folder, checkfn):
    if not path.exists(folder):
        return

    check_call(["rm", "-rf"] + [path.join(folder, file) for file in listdir(folder) if not checkfn(file)])

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
        updateCheckerEvent.wait(timeout=600)

def stdinChecker():
    for line in stdin:
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

while server.poll(waitTime=1):
    pass

fireUpdateChecker()
updateCheckerThread.join()
