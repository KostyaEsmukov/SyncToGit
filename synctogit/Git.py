from __future__ import absolute_import

import os

import git

from .GitTransaction import GitTransaction


class GitException(Exception):
    pass


os.environ['USERNAME'] = 'None'  # default username for git


def gitRepo(d):
    r = git.Repo(d)
    if os.path.normpath(d + os.sep + ".git") != os.path.normpath(r.git_dir):  # parent git root chosen
        return None
    return r


class Git:
    def __init__(self, repo_dir, branch, push):
        repo_dir = os.path.realpath(repo_dir) + os.sep

        self.conf = {
            'repo_dir': repo_dir,
            'branch': branch,
            'push': push
        }
        self.git = self._check_init_git(repo_dir)

    @staticmethod
    def _init_git_repo(d):
        g = git.Repo.init(d)
        g.index.commit("Initial commit")
        return g

    @staticmethod
    def _check_init_git(d):
        if not os.path.isdir(d):
            raise GitException("Git directory does not exists: %s. You should create it manually." % d)

        try:
            r = gitRepo(d) or Git._init_git_repo(d)
            return r
        except:
            if len(os.listdir(d)) > 0:
                raise GitException("Git directory is not a git repo and is not empty")
            else:
                return Git._init_git_repo(d)

    def transaction(self):
        """
        with git.transaction() as t:
            ...
        """
        return GitTransaction(self.git, **self.conf)
