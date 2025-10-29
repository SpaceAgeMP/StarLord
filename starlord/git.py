from subprocess import check_call, check_output
from os import path
from starlord.updateable import UpdateableResource

class GitRepo(UpdateableResource):
    repo: str
    branch: str

    def __init__(self, folder: str, repo: str, branch: str):
        super().__init__(folder, repo)

        self.repo = repo
        self.branch = branch

    def checkUpdate(self, offline: bool=False) -> bool:
        if not path.exists(self.folder):
            return True

        if not offline:
            _ = check_call(["git", "-C", self.folder, "remote", "set-url", "origin", self.repo])
            _ = check_call(["git", "-C", self.folder, "fetch", "origin"])

        return self._rev_parse("HEAD") != self._rev_parse("origin/%s" % self.branch)

    def update(self):
        if not path.exists(self.folder):
            _ = check_call(["git", "clone", self.repo, self.folder])
        _ = check_call(["git", "-C", self.folder, "reset", "--hard", "origin/%s" % self.branch])

    def _rev_parse(self, rev: str):
        return check_output(["git", "-C", self.folder, "rev-parse", rev]).strip()
