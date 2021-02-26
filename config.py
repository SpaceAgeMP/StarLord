from os import path
from yaml import safe_load as yaml_load

CONFIG_DIR = path.join(path.dirname(__file__), "config")

class Config:
    def __init__(self):
        self.inherit = None
        self.server = ServerConfig()
        self.addons = []

class AddonConfig:
    def __init__(self):
        self.name = None
        self.repo = None
        self.private = False
        self.trusted = False

class ServerConfig:
    def __init__(self):
        self.tickrate = 60
        self.maxplayers = 32
        self.map = "gm_flatgrass"
        self.ip = "0.0.0.0"
        self.workshop_clients = None
        self.workshop_server = None
        self.gamemode = "sandbox"

def dict_to_obj(dict, o):
    for k in dict:
        setattr(o, k, dict[k])
    return o

def obj_to_config(dict):
    cfg = Config()
    if "inherit" in dict:
        cfg.inherit = dict["inherit"]
    if "addons" in dict:
        for addon in dict["addons"]:
            cfg.addons.append(dict_to_obj(addon, AddonConfig()))
    if "server" in dict:
        cfg.server = dict_to_obj(dict["server"], ServerConfig())
    return cfg

def merge_object(o1, o2):
    if not o2:
        return
    d = vars(o2)
    for k in d:
        v = d[k]
        if v != None:
            setattr(o1, k, d[k])

def _load(config):
    fh = open(path.join(CONFIG_DIR, "%s.yml" % config))
    data = fh.read()
    fh.close()
    return obj_to_config(yaml_load(data))

def load(config):
    cfgStack = []
    nextCfg = config
    while nextCfg:
        cfg = _load(nextCfg)
        cfgStack.append(cfg)
        nextCfg = cfg.inherit

    cfg = Config()
    while len(cfgStack) > 0:
        nextCfg = cfgStack.pop()
        merge_object(cfg.server, nextCfg.server)
        for addon in nextCfg.addons:
            addonCfg = AddonConfig()
            merge_object(addonCfg, addon)
            cfg.addons.append(addonCfg)
    cfg.inherit = None
    return cfg
