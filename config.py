from os import path
from yaml import safe_load as yaml_load
from typing import Any, Mapping, TypeVar, cast

CONFIG_DIR = path.abspath(path.join(path.dirname(__file__), "config"))

class Config:
    inherit: str | None
    server: "ServerConfig"
    addons: list["AddonConfig"]
    luabins: list["LuaBinConfig"]

    def __init__(self):
        super().__init__()
        self.inherit = None
        self.server = ServerConfig()
        self.addons = []
        self.luabins = []

    def defaults(self):
        self.server.defaults()
        for addon in self.addons:
            addon.defaults()
        for luabin in self.luabins:
            luabin.defaults()

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

    def defaults(self):
        self.private = False
        self.trusted = False
        self.branch = "main"
        self.gamemodes = []

class LuaBinConfig:
    name: str = ""
    type: str = ""
    config: Mapping[str, Any]

    def __init__(self):
        super().__init__()
        self.config = {}

    def defaults(self):
        self.config = {}

class ServerConfig:
    tickrate: int
    maxplayers: int
    map: str
    ip: str
    port: int
    workshop_clients: str | None
    workshop_server: str | None
    gamemode: str
    restart_every: str | None

    def __init__(self):
        super().__init__()
        self.tickrate = 60
        self.maxplayers = 32
        self.map = "gm_flatgrass"
        self.ip = "0.0.0.0"
        self.port = 27015
        self.workshop_clients = None
        self.workshop_server = None
        self.gamemode = "sandbox"
        self.restart_every = None

    def defaults(self):
        self.tickrate = 60
        self.maxplayers = 32
        self.map = "gm_flatgrass"
        self.ip = "0.0.0.0"
        self.port = 27015
        self.gamemode = "sandbox"

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
            ac = AddonConfig()
            ac.defaults()
            cfg.addons.append(dict_to_obj(addon, ac))
    if "luabins" in dict:
        for luabin in dict["luabins"]:
            lbc = LuaBinConfig()
            lbc.defaults()
            cfg.luabins.append(dict_to_obj(luabin, lbc))
    if "server" in dict:
        cfg.server = dict_to_obj(dict["server"], ServerConfig())
    return cfg

def merge_object(o1: Any, o2: Any):
    if not o2:
        return
    d = cast(Mapping[Any, Any], vars(o2))
    for k in d:
        v = d[k]
        if v != None:
            setattr(o1, k, v)

def _load(config: str) -> Config:
    fh = open(path.join(CONFIG_DIR, "%s.yml" % config))
    data = fh.read()
    fh.close()
    return obj_to_config(yaml_load(data))

def load(config: str):
    cfgStack: list[Config] = []
    nextCfg = config
    while nextCfg:
        cfg = _load(nextCfg)
        cfgStack.append(cfg)
        nextCfg = cfg.inherit

    cfg = Config()
    cfg.defaults()
    while len(cfgStack) > 0:
        nextCfg = cfgStack.pop()
        merge_object(cfg.server, nextCfg.server)
        for addon in nextCfg.addons:
            addonCfg = AddonConfig()
            merge_object(addonCfg, addon)
            cfg.addons.append(addonCfg)
        for luabin in nextCfg.luabins:
            luaBinCfg = LuaBinConfig()
            merge_object(luaBinCfg, luabin)
            cfg.luabins.append(luaBinCfg)

    cfg.inherit = None

    return cfg
