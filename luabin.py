from platform import architecture, system
from json import loads as json_loads, load as json_load, dump as json_dump
from os.path import join
from os import makedirs, getenv
from traceback import print_exception
from requests import get as http_get
from config import LuaBinConfig
from updateable import UpdateableResource
from typing import Any, Mapping

usedDLLs: set[str] = set()

class LuaBin(UpdateableResource):
    storage: Any

    def __init__(self, folder: str, name: str) -> None:
        super().__init__(folder, name)
        self.disable_updates = getenv(f"DISABLE_UPDATE_LUABIN_{self.name.upper()}", "") == "true"
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
        makedirs(self.folder, exist_ok=True)
        file = self.formatPath(self.makeMetaName())
        with open(file, "w") as f:
            json_dump(self.storage, f)
        
    def formatPath(self, name: str):
        return join(self.folder, name)

    def makeBinaryName(self):
        arch_suffix = ""
        if architecture()[0] == "64bit":
            arch_suffix = "64"

        system_name = system()

        platform_suffix = ""
        if system_name == "Windows":
            # Windows is the only platform with a 32-bit suffix
            # for some reason, thanks GMod
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

    def __init__(self, folder: str, name: str, config: Mapping[str, Any]):
        super().__init__(folder, name)
        self.repo_org = config["org"]
        self.repo_name = config["name"]

        if "tag" in config:
            self.fixed_tag = config["tag"]
            self.release = f"tags/{self.fixed_tag}"
        else:
            self.fixed_tag = None
            self.release = "latest"

    def queryReleaseInfo(self, use_release: str | None = None):
        if use_release is None:
            use_release = self.fixed_tag

        if use_release is not None:
            release = self.storage.get("release", None)
            if release is not None and release["tag_name"] == use_release:
                return release

        res = http_get(url=f"https://api.github.com/repos/{self.repo_org}/{self.repo_name}/releases/{self.release}")
        res.raise_for_status()

        release = json_loads(res.text)

        self.storage["release"] = release
        self.save()

        return release

    def isReleaseInstalled(self, release: dict[str, Any]):
        return release["tag_name"] == self.storage.get("tag_name", "")
        
    def storeRelease(self, release: dict[str, Any]):
        self.storage["tag_name"] = release["tag_name"]
        self.save()

    def getBinaryURL(self, release: dict[str, Any]):
        binary_name = self.makeBinaryName()
        for asset in release["assets"]:
            if asset["name"] == binary_name:
                return asset["browser_download_url"]
        return None

    def checkUpdate(self, offline: bool = False):
        if self.disable_updates:
            return False

        if offline:
            release = self.storage.get("release", None)
            if release is None:
                return True
        else:
            release = self.queryReleaseInfo()

        if self.isReleaseInstalled(release):
            return False
        if self.getBinaryURL(release) is None:
            print("Found update, but no binary, pointless to update", flush=True)
            return False
        return True

    def update(self):
        if self.disable_updates:
            return

        release = self.storage.get("release", None)
        if release is None:
            release = self.queryReleaseInfo()

        if self.isReleaseInstalled(release):
            return

        url = self.getBinaryURL(release)
        if url is None:
            print("LuaBin manifest missing binaries, ignoring", flush=True)
            return

        resp = http_get(url=url, stream=True)
        resp.raise_for_status()
        with open(self.formatPath(self.makeBinaryName()), "wb") as f:
            _ = f.write(resp.content)

        self.storeRelease(release)

def makeLuaBin(folder: str, config: LuaBinConfig):
    if config.type == "github_release":
        return GithubReleaseLuaBin(folder, config.name, config.config)
    else:
        raise ValueError(f"{config.type} is an invalid LuaBin type")

def isDLLUsed(dll: str):
    return dll in usedDLLs
