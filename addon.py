from git import GitRepo
from updateable import UpdateableResource
from os import mkdir, path, symlink, listdir, getenv
from utils import unlink_safe
from shutil import copyfile
from config import AddonConfig

usedGamemodes: set[str] = set()
usedAddons: set[str] = set()

usedGamemodes.add("base")
usedGamemodes.add("sandbox")
usedGamemodes.add("terrortown")

class Addon(UpdateableResource):
    def __init__(self, config: AddonConfig):
        super().__init__("garrysmod/addons/%s" % config.name.lower(), config.name)

        self.nameLower = self.name.lower()
        self.trusted = config.trusted
        self.gamemodes = config.gamemodes
        self.disable_updates = getenv(f"DISABLE_UPDATE_ADDON_{self.name.upper()}", "") == "true"

        if config.repo:
            self.repo = config.repo
        elif config.private:
            self.repo = "git@github.com:SpaceAgeMP/%s" % config.name
        else:
            self.repo = "https://github.com/SpaceAgeMP/%s" % config.name
        self.branch = config.branch
        self.git = GitRepo(self.folder, self.repo, self.branch)

        for gamemode in self.gamemodes:
            usedGamemodes.add(gamemode)
        usedAddons.add(self.nameLower)

    def checkUpdate(self, offline: bool = False):
        if self.disable_updates:
            return False
        return self.git.checkUpdate(offline)

    def update(self):
        if not self.disable_updates:
            self.git.update()

        for gamemode in self.gamemodes:
            gamemodeFolder = "%s/gamemodes/%s" % (self.folder, gamemode)
            link = "garrysmod/gamemodes/%s" % gamemode
            _ = unlink_safe(link)
            symlink("../../%s" % gamemodeFolder, link, False)

        cfgFolder = "%s/cfg" % self.folder
        if self.trusted and path.exists(cfgFolder):
            gameCfgFolder = "garrysmod/cfg"
            if not path.exists(gameCfgFolder):
                mkdir(gameCfgFolder)
            for cfg in listdir(cfgFolder):
                print("CONFIG INJECT", cfgFolder, gameCfgFolder, cfg, flush=True)
                _ = copyfile("%s/%s" % (cfgFolder, cfg), "%s/%s" % (gameCfgFolder, cfg))


def isGamemodeUsed(gamemode: str):
    return gamemode in usedGamemodes

def isAddonUsed(addon: str):
    return addon in usedAddons
