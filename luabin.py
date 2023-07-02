from platform import architecture, system
from json import loads as json_loads, load as json_load, dump as json_dump
from os.path import join
from traceback import print_exception
from requests import get as http_get
from config import LuaBinConfig

usedDLLs = set()

class LuaBin:
    name: str

    def __init__(self, folder, name):
        self.folder = folder
        self.name = name
        self.load()

    def load(self):
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
        if architecture()[0] == 64:
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

    def queryLatestRelease(self):
        res = http_get(url=f"https://api.github.com/repos/{self.repo_org}/{self.repo_name}/releases/latest")
        res.raise_for_status()
        return json_loads(res.text)

    def isReleaseInstalled(self, release):
        return release["tag_name"] == self.storage.get("tag_name", "")
        
    def storeRelease(self, release):
        self.storage["tag_name"] = release
        self.save()

    def checkUpdate(self, offline=False):
        return not self.isReleaseInstalled(self.queryLatestRelease())

    def update(self):
        binary_name = self.makeBinaryName()
        usedDLLs.add(binary_name)

        release = self.queryLatestRelease()
        if self.isReleaseInstalled(release):
            return

        url = None
        for asset in release["assets"]:
            print(asset["name"], binary_name, asset)
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
