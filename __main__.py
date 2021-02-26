from server import ServerProcess
from addon import Addon, isGamemodeUsed
from config import load

config = load("spaceage_forlorn")
server = ServerProcess(".", config.server)

addons = []
for addonCfg in config.addons:
    addons.append(Addon(addonCfg))

#server.update()

#server.switchTo()

#addon = Addon("SpaceAge", None, True)
#addon.update()


#server.run()
#while server.poll():
#    pass
