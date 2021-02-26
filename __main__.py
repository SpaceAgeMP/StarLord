from subprocess import call
from server import ServerProcess
from addon import Addon, isAddonUsed, isDLLUsed, isGamemodeUsed
from config import load
from os import listdir, path, getenv
from time import sleep
from threading import Thread
from sys import stdin

config = load(getenv("STARLORD_CONFIG"))
server = ServerProcess(".", config.server)

addons = []
for addonCfg in config.addons:
    addons.append(Addon(addonCfg))

def runUpdates():
    server.updateBin()
    server.switchTo()
    for addon in addons:
        addon.update()

def checkUpdates():
    hasUpdates = False
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
    print("Checking for updates...")
    hasUpdates = checkUpdates()
    if hasUpdates:
        server.exec("restart_if_empty 1")

    for _ in range(0, 600):
        if not server.running:
            return
        sleep(1)

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

updateCheckerThread.join()
