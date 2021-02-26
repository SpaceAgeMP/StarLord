from git import GitRepo
from os import mkdir, path, symlink, listdir
from utils import unlink_safe

usedDLLs = set()
usedGamemodes = set()

class Addon:
    def __init__(self, config):
        self.name = config.name
        self.nameLower = config.name.lower()
        self.folder = "garrysmod/addons/%s" % self.nameLower
        if config.repo:
            self.repo = config.repo
        elif config.private:
            self.repo = "git@github.com:SpaceAgeMP/%s" % config.name
        else:
            self.repo = "https://github.com/SpaceAgeMP%s" % config.name
        self.trusted = config.trusted
        self.git = GitRepo(self.folder, self.repo)

    def update(self):
        if not self.git.update():
            return

        gamemodeFolder = "%s/gamemodes/%s" % (self.folder, self.nameLower)
        if path.exists(gamemodeFolder):
            link = "garrysmod/gamemodes/%s" % self.nameLower
            unlink_safe(link)
            symlink("../../%s" % gamemodeFolder, link, False)
            usedGamemodes.add(self.nameLower)

        binFolder = "%s/lua/bin" % self.folder
        if self.trusted and path.exists(binFolder):
            gameBinFolder = "garrysmod/lua/bin"
            if not path.exists(gameBinFolder):
                mkdir(gameBinFolder)
            for dll in listdir(binFolder):
                dllLink = "%s/%s" % (gameBinFolder, dll)
                unlink_safe(dllLink)
                symlink("../../../%s/%s" % (binFolder, dll), dllLink, False)
                usedDLLs.add(dll)

def isDLLUsed(dll):
    return dll in usedDLLs

def isGamemodeUsed(gamemode):
    return gamemode in usedGamemodes
