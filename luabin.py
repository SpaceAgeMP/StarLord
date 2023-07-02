from platform import architecture, system
from json import loads as json_loads, load as json_load, dump as json_dump
from os.path import join
from traceback import print_exception
from requests import get as http_get
from config import LuaBinConfig
from requests.exceptions import HTTPError

usedDLLs = set()

class LuaBin:
    name: str

    def __init__(self, folder, name):
        self.folder = folder
        self.name = name
        self.load()

    def load(self):
        usedDLLs.add(self.makeBinaryName())
        usedDLLs.add(self.makeMetaName())

        file = self.formatPath(self.makeMetaName())
        try:
            with open(file, "r") as f:
                self.storage = json_load(f)
        except FileNotFoundError as e:
            self.storage = {}
        except Exception as e:
            print_exception(e)
            self.storage = {}

    def save(self):
        file = self.formatPath(self.makeMetaName())
        with open(file, "w") as f:
            json_dump(self.storage, f)
        
    def formatPath(self, name):
        return join(self.folder, name)

    def makeBinaryName(self):
        arch_suffix = ""
        if architecture()[0] == "64bit":
            arch_suffix = "64"

        system_name = system()

        platform_suffix = ""
        if system_name == "Windows":
            if arch_suffix == "":
                arch_suffix = "32"
            platform_suffix = "win"
        elif system_name == "Linux":
            platform_suffix = "linux"
        elif system_name == "Darwin":
            platform_suffix = "osx"

        return f"gmsv_{self.name}_{platform_suffix}{arch_suffix}.dll"

    def makeMetaName(self):
        return f"{self.makeBinaryName()}.meta"

class GithubReleaseLuaBin(LuaBin):
    repo_org: str
    repo_name: str

    def __init__(self, folder, name, config):
        super().__init__(folder, name)
        self.repo_org = config["org"]
        self.repo_name = config["name"]

        if "tag" in config:
            self.fixed_tag = config["tag"]
            self.release = f"tags/{self.fixed_tag}"
        else:
            self.fixed_tag = None
            self.release = "latest"

    def queryReleaseInfo(self):
        if self.fixed_tag is not None:
            release = self.storage.get("release", None)
            if release is not None and release["tag_name"] == self.fixed_tag:
                return release

        res = http_get(url=f"https://api.github.com/repos/{self.repo_org}/{self.repo_name}/releases/{self.release}")
        res.raise_for_status()

        release = json_loads(res.text)

        self.storage["release"] = release
        self.save()

        return release

    def isReleaseInstalled(self, release):
        return release["tag_name"] == self.storage.get("tag_name", "")
        
    def storeRelease(self, release):
        self.storage["tag_name"] = release["tag_name"]
        self.save()

    def checkUpdate(self, offline=False):
        if offline:
            release = self.storage.get("release", None)
            if release is None:
                return True
        else:
            release = self.queryReleaseInfo()
        return not self.isReleaseInstalled(release)

    def update(self):
        release = self.storage.get("release", None)
        if release is None:
            release = self.queryReleaseInfo()

        if self.isReleaseInstalled(release):
            return

        url = None
        binary_name = self.makeBinaryName()
        for asset in release["assets"]:
            if asset["name"] == binary_name:
                url = asset["browser_download_url"]
                break

        resp = http_get(url=url, stream=True)
        resp.raise_for_status()
        with open(self.formatPath(self.makeBinaryName()), "wb") as f:
            f.write(resp.content)

        self.storeRelease(release)

def makeLuaBin(folder, config: LuaBinConfig):
    if config.type == "github_release":
        return GithubReleaseLuaBin(folder, config.name, config.config)
    else:
        raise ValueError(f"{config.type} is an invalid LuaBin type")

def isDLLUsed(dll):
    return dll in usedDLLs
