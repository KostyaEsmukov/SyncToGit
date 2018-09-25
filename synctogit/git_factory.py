import os
from typing import Optional

import git


class GitError(Exception):
    pass


# XXX is this still relevant?
os.environ['USERNAME'] = 'None'  # default username for git


def git_factory(
    repo_dir: str,
    *,
    branch: str = "master",
    remote_name: str = "origin",
    remote: str = None
) -> git.Repo:
    return _GitFactory(
        repo_dir=repo_dir, branch=branch, remote_name=remote_name, remote=remote
    ).git


class _GitFactory:
    def __init__(
        self, repo_dir: str, *, branch: str, remote_name: str, remote: Optional[str]
    ) -> None:
        repo_dir = os.path.realpath(repo_dir) + os.sep

        self.repo_dir = repo_dir
        self.branch = branch
        self.remote_name = remote_name
        self.remote = remote
        self.git = self._check_init_git()

    def _check_init_git(self):
        if not os.path.isdir(self.repo_dir):
            raise GitError(
                "Git directory %s does not exist. "
                "You should create it manually." % self.repo_dir
            )

        try:
            return self._load_existing_git_repo()
        except GitError:
            raise
        except git.exc.InvalidGitRepositoryError as e:
            if os.listdir(self.repo_dir):
                raise GitError("Git directory is not a git repo and is not empty")
            # else -- the repo dir is empty -- let's create the new repo.
        return self._init_new_git_repo()

    def _load_existing_git_repo(self) -> git.Repo:
        repo = git.Repo(self.repo_dir)
        expected_path = os.path.normpath(self.repo_dir + os.sep + ".git")
        chosen_path = os.path.normpath(repo.git_dir)
        # Ensure that the chosen Git repo is not some other higher level repo.
        assert chosen_path == expected_path

        git_branch = repo.active_branch.name
        if git_branch != self.branch:
            raise GitError(
                'HEAD points to a different branch "%s" '
                'than requested "%s"' % (git_branch, self.branch)
            )
        if not repo.head.is_valid():
            raise GitError(
                "The chosen git branch is empty. Create an initial "
                "commit manually or simply delete the .git directory."
            )
        self._ensure_remote(repo)
        return repo

    def _init_new_git_repo(self) -> git.Repo:
        repo = git.Repo.init(self.repo_dir)
        # Create orphan branch
        repo.head.reference = git.Head(repo, "refs/heads/%s" % self.branch)
        repo.index.commit("Initial commit")
        self._ensure_remote(repo)
        return repo

    def _ensure_remote(self, repo: git.Repo) -> None:
        if not self.remote:
            return
        try:
            origin = repo.remotes[self.remote_name]
        except IndexError:
            origin = repo.create_remote(self.remote_name, self.remote)
        else:
            if origin.url != self.remote:
                raise GitError(
                    'Git remote "%s %s" dosn\'t match the expected "%s".'
                    % (self.remote_name, origin.url, self.remote)
                )
        assert origin.exists()
