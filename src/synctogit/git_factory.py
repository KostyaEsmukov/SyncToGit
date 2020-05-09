import contextlib
import os
from typing import Optional

import git


class GitError(Exception):
    pass


# Default username and email for git.
os.environ["USERNAME"] = "synctogit"
os.environ["EMAIL"] = "none@none"


gitignore_synctogit_files_prefix = ".synctogit"

# The directory below is automatically added to the .gitignore file,
# so feel free to store any local cache of a service here.
local_git_ignored_cache_dir = "%s.sync_cache" % gitignore_synctogit_files_prefix


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
        except git.exc.InvalidGitRepositoryError:
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
        self._ensure_gitignore(repo)
        return repo

    def _init_new_git_repo(self) -> git.Repo:
        repo = git.Repo.init(self.repo_dir)
        # Create orphan branch
        repo.head.reference = git.Head(repo, "refs/heads/%s" % self.branch)
        self._ensure_gitignore(repo)
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

    def _ensure_gitignore(self, repo: git.Repo) -> None:
        gitignore_path = os.path.join(self.repo_dir, ".gitignore")

        gitignore_line = "%s*" % gitignore_synctogit_files_prefix

        if os.path.isfile(gitignore_path):
            with open(gitignore_path, "rt") as f:
                gitignore = f.read()
            for line in gitignore.splitlines():
                if line.rstrip() == gitignore_line:
                    # gitignore is good!
                    return

        with self.clean_index(repo, [".gitignore"]):
            with open(gitignore_path, "at") as f:
                f.write("\n%s\n" % gitignore_line)
            repo.index.add([".gitignore"])
            repo.index.commit("Update .gitignore (automated commit by synctogit)")

    @contextlib.contextmanager
    def clean_index(self, repo: git.Repo, fail_for_changed_files=[]):
        changes = repo.git.status(
            *fail_for_changed_files, porcelain=True, untracked_files=True
        )
        if changes:
            raise GitError(
                "Unable to make modifications because they already "
                "contain uncommitted changes. Please commit them or reset "
                "manually. The list of conflicts:\n%s" % changes
            )

        stash = repo.is_dirty()
        if stash:
            repo.git.stash()
        try:
            yield
        finally:
            if stash:
                repo.git.stash("pop", "--index")
