from socket import timeout
from git import GitRepo
from subprocess import call
from server import ServerProcess
from addon import Addon, isAddonUsed, isDLLUsed, isGamemodeUsed
from config import load
from os import listdir, path, getenv
from time import sleep
from threading import Thread, Event
from sys import stdin
from signal import SIGINT, SIGTERM, SIGHUP, SIGUSR1, SIGUSR2, signal

FOLDER = path.abspath(path.dirname(__file__))
selfRepo = GitRepo(FOLDER, "https://github.com/SpaceAgeMP/StarLord.git")

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

def runUpdates():
    server.updateBin()
    server.switchTo()
    for addon in addons:
        addon.update()

def checkUpdates():
    hasUpdates = selfRepo.checkUpdate()
    if hasUpdates:
        selfRepo.update()
    for addon in addons:
        if addon.checkUpdate():
            hasUpdates = True
    server.updateWorkshopLua()
    return hasUpdates

def cleanupFolder(folder, checkfn):
    if not path.exists(folder):
        return

    toDeleteList = []
    for file in listdir(folder):
        if not checkfn(file):
            toDeleteList.append(path.join(folder, file))

    for toDelete in toDeleteList:
        call(["rm", "-rf", toDelete])

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
        hasUpdates = checkUpdates()
        if hasUpdates:
            server.restartIfEmpty()

        updateCheckerEvent = Event()
        updateCheckerEvent.wait(timeout=600)

def stdinChecker():
    for line in stdin:
        server.exec(line.strip())

updateCheckerThread = Thread(target=updateChecker, name="Update checker")
updateCheckerThread.start()

if stdin.isatty():
    stdinThread = Thread(target=stdinChecker, name="STDIN reader", daemon=True)
    stdinThread.start()

while server.poll(waitTime=1):
    pass

fireUpdateChecker()
updateCheckerThread.join()
