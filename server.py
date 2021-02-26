from os import chdir, path
from sys import stdout, stderr
from subprocess import PIPE, Popen, call
from sys import stdout
from tempfile import NamedTemporaryFile
from threading import Thread
from queue import Queue, Empty

STREAM_STDOUT = 0
STREAM_STDERR = 1

class ServerProcess:
    def __init__(self, folder):
        self.folder = path.abspath(folder)

        self.pidfile = path.join(self.folder, "pid")
        self.proc = None
        self.stdoutThread = None
        self.stderrThread = None
        self.stdioQueue = None

        self.tickrate = 20
        self.maxplayers = 16
        self.map = "sb_gooniverse_v4"
        self.ip = "0.0.0.0"
        self.workshop_clients = "177294269"
        self.workshop_server = "2371557248"
        self.gamemode = "spaceage"

    def switchTo(self):
        chdir(self.folder)

    def update(self):
        self.switchTo()

        steamcmdScript = """
@ShutdownOnFailedCommand 1
@NoPromptForPassword 1
login anonymous
force_install_dir %s
app_update 4020 -beta x86-64
quit
""" % path.abspath(".")

        tmpFile = NamedTemporaryFile(mode="w+", suffix=".txt")

        tmpFile.write(steamcmdScript)
        tmpFile.flush()
        try:
            call(["steamcmd", "+runscript", tmpFile.name])
        finally:
            tmpFile.close()

    def run(self):
        self.switchTo()

        args = ["./bin/linux64/srcds",
                    "-usercon", "-autoupdate", "-disableluarefresh", "-console",
                    "-tickrate", "%i" % self.tickrate, "-game", "garrysmod", "+ip", self.ip, "+maxplayers", "%i" % self.maxplayers,
                    "+map", self.map, "+host_workshop_collection", self.workshop_server, "+gamemode", self.gamemode
        ]
        env = {
            "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/game",
            "LD_LIBRARY_PATH": path.abspath("./bin/linux64"),
        }

        self.kill()

        self.stdioQueue = Queue()
        self.stdoutThread = Thread(target=self._read_stdout)
        self.stderrThread = Thread(target=self._read_stderr)
        self.stdoutThread.daemon = True
        self.stderrThread.daemon = True
        self.proc = Popen(args, env=env, stdout=PIPE, stderr=PIPE, stdin=PIPE, close_fds=True, encoding='utf-8')
        self.stdoutThread.start()
        self.stderrThread.start()

    def _read_stdout(self):
        for line in self.proc.stdout:
            self.stdioQueue.put((line, STREAM_STDOUT))

    def _read_stderr(self):
        for line in self.proc.stderr:
            self.stdioQueue.put((line, STREAM_STDERR))

    def kill(self):
        if self.proc:
            try:
                self.proc.kill()
            except ProcessLookupError:
                pass
            self.proc = None
            
        if self.stdoutThread:
            self.stdoutThread.join()
            self.stdoutThread = None
        if self.stderrThread:
            self.stderrThread.join()
            self.stderrThread = None

        if self.stdioQueue:
            self.stdioQueue = None

    def poll(self):
        if not self.proc:
            return False

        try:
            out = self.stdioQueue.get_nowait()
            fh = None
            if out[1] == STREAM_STDOUT:
                fh = stdout
            elif out[1] == STREAM_STDERR:
                fh = stderr
            fh.write(out[0])
            fh.flush()
        except Empty:
            pass

        if self.proc.poll() != None:
            self.kill()
            return False
        return True
