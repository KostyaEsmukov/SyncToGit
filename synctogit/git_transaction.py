import logging
from datetime import datetime
from pathlib import Path

import git

logger = logging.getLogger(__name__)


def rmfile_silent(path: Path) -> None:
    try:
        path.unlink()
    except OSError as e:
        logger.warn("Unable to delete %s file: %s" % (path, repr(e)))


class GitSimultaneousTransaction(Exception):
    pass


class GitTransaction:
    # Must be thread-safe.

    def __init__(self, repo: git.Repo, push: bool, remote_name: str) -> None:
        self.git = repo
        self.push = push

        self.repo_dir = Path(repo.working_tree_dir)
        self.lockfile_path = self.repo_dir / ".synctogit.lockfile"

        self.transaction_commit_message = None

    def __enter__(self):
        if self.lockfile_path.is_file():
            raise GitSimultaneousTransaction(
                "Lockfile exists. Another copy of program is probably running. "
                "Remove this file if you are sure that this is "
                "a mistake: %s" % self.lockfile_path
            )

        self._stash()
        self.lockfile_path.write_bytes(b"1")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        rmfile_silent(self.lockfile_path)

        if exc_type is not None:
            logger.warning(
                "git transaction failed: %s(%s)" % (repr(exc_type), exc_val)
            )
            self._stash()
        else:
            if self.git.is_dirty(untracked_files=True):
                self._commit_changes()

            self._push()

    def remove_dirs_until_not_empty(self, path: Path) -> None:
        assert self.repo_dir.is_absolute()
        assert path.is_absolute()

        # raises ValueError if path is not within repo_dir
        path.relative_to(self.repo_dir)

        while path != self.repo_dir:
            try:
                path.rmdir()  # raises if directory is not empty
            except OSError:
                break

    def _stash(self):
        if self.git.is_dirty(untracked_files=True):
            logger.warning(
                "Git repo is dirty. Working copy is going to be be stashed."
            )

            self.git.git.stash('--include-untracked')

    def _commit_changes(self):
        # I've had some issues with charset under Windows when using
        # the python version: self.git.index.add("*")
        self.git.git.add(["-A", "."])
        message = self.transaction_commit_message
        if not message:
            message = "Sync at %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.git.index.commit(message)

    def _push(self):
        if not self.push:
            return
        try:
            self.git.remotes[self.remote_name].push()
        except Exception as e:
            logger.warning("Failed to git push: %s", repr(e))
