from subprocess import check_call, check_output
from os import path

class GitRepo:
    def __init__(self, folder, repo, branch):
        self.folder = folder
        self.repo = repo
        self.branch = branch

    def _rev_parse(self, rev):
        return check_output(["git", "-C", self.folder, "rev-parse", rev]).strip()

    def checkUpdate(self, offline=False):
        if not path.exists(self.folder):
            return True

        if not offline:
            check_call(["git", "-C", self.folder, "remote", "set-url", "origin", self.repo])
            check_call(["git", "-C", self.folder, "fetch", "origin"])

        return self._rev_parse("HEAD") != self._rev_parse("origin/%s" % self.branch)

    def _clone(self):
        check_call(["git", "clone", self.repo, self.folder])

    def _update(self):
        check_call(["git", "-C", self.folder, "reset", "--hard", "origin/%s" % self.branch])

    def update(self):
        if not path.exists(self.folder):
            self._clone()
        self._update()
