from server import ServerProcess
from addon import Addon, isGamemodeUsed

server = ServerProcess(".")
#server.update()

server.switchTo()

addon = Addon("SpaceAge", None, True)
#addon.update()


server.run()
while server.poll():
    pass
