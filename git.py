from subprocess import call
from os import path

class GitRepo:
    def __init__(self, folder, repo):
        self.folder = folder
        self.repo = repo
    
    def _clone(self):
        call(["git", "clone", self.repo, self.folder])
        return True

    def _update(self):
        call(["git", "-C", self.folder, "remote", "set-url", "origin", self.repo])
        call(["git", "-C", self.folder, "pull"])
        # TODO: Return if this actually updated, and not True all the time
        return True

    def update(self):
        if path.exists(self.folder):
            return self._update()
        return self._clone()
