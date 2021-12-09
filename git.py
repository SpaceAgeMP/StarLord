from subprocess import call, check_output
from os import path

class GitRepo:
    def __init__(self, folder, repo):
        self.folder = folder
        self.repo = repo
        self.branch = "master"

    def _rev_parse(self, rev):
        return check_output(["git", "-C", self.folder, "rev-parse", rev]).strip()

    def checkUpdate(self, offline=False):
        if not path.exists(self.folder):
            return True

        if not offline:
            call(["git", "-C", self.folder, "remote", "set-url", "origin", self.repo])
            try:
                call(["git", "-C", self.folder, "fetch", "origin"])
            except:
                pass

        return self._rev_parse("HEAD") != self._rev_parse("origin/%s" % self.branch)

    def _clone(self):
        call(["git", "clone", self.repo, self.folder])

    def _update(self):
        call(["git", "-C", self.folder, "reset", "--hard", "origin/%s" % self.branch])

    def update(self):
        if path.exists(self.folder):
            self._update()
        else:
            self._clone()
