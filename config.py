from os import path
from yaml import safe_load as yaml_load
from typing import Any, Mapping, TypeVar, cast

CONFIG_DIR = path.abspath(path.join(path.dirname(__file__), "config"))

class Config:
    inherit: str | None = None
    server: "ServerConfig"
    addons: list["AddonConfig"]
    luabins: list["LuaBinConfig"]

    def __init__(self):
        super().__init__()
        self.server = ServerConfig()
        self.addons = []
        self.luabins = []

class AddonConfig:
    name: str = ""
    repo: str = ""
    private: bool = False
    trusted: bool = False
    branch: str = "main"
    gamemodes: list[str]

    def __init__(self):
        super().__init__()
        self.gamemodes = []

class LuaBinConfig:
    name: str = ""
    type: str = ""
    config: Mapping[str, Any]

    def __init__(self):
        super().__init__()
        self.config = {}

class ServerConfig:
    tickrate: int = 60
    maxplayers: int = 32
    map: str = "gm_flatgrass"
    ip: str = "0.0.0.0"
    port: int = 27015
    workshop_clients: str | None = None
    workshop_server: str | None = None
    gamemode: str = "sandbox"
    restart_every: str | None = None

T = TypeVar("T")
def dict_to_obj(dict: Mapping[Any, Any], o: T) -> T:
    for k in dict:
        setattr(o, k, dict[k])
    return o

def obj_to_config(dict: Mapping[str, Any]):
    cfg = Config()
    if "inherit" in dict:
        cfg.inherit = dict["inherit"]
    if "addons" in dict:
        for addon in dict["addons"]:
            cfg.addons.append(dict_to_obj(addon, AddonConfig()))
    if "luabins" in dict:
        for luabin in dict["luabins"]:
            cfg.luabins.append(dict_to_obj(luabin, LuaBinConfig()))
    if "server" in dict:
        cfg.server = dict_to_obj(dict["server"], ServerConfig())
    return cfg

def _load(config: str) -> Mapping[str, Any]:
    with open(path.join(CONFIG_DIR, "%s.yml" % config)) as fh:
        data = fh.read()
    return yaml_load(data)

def load(configName: str):
    cfgStack: list[Mapping[str, Any]] = []
    nextCfgName = configName
    while nextCfgName:
        cfg = _load(nextCfgName)
        cfgStack.append(cfg)
        nextCfgName = cfg.get("inherit", None)

    mergedCfg: Mapping[str, Any] = {
        "server": {},
        "addons": [],
        "luabins": [],
    }
    while len(cfgStack) > 0:
        nextCfg = cfgStack.pop()

        mergedCfg["addons"] += nextCfg.get("addons", [])
        mergedCfg["luabins"] += nextCfg.get("luabins", [])
        cast(dict[str, Any], mergedCfg["server"]).update(nextCfg.get("server", {}))

    return obj_to_config(mergedCfg)
