import contextlib
import datetime
import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from synctogit.git_factory import git_factory
from synctogit.git_transaction import (
    GitPushError,
    GitSimultaneousTransaction,
    GitTransaction,
)

initial_commit = "Update .gitignore (automated commit by synctogit)"


@pytest.fixture
def git_repo(temp_dir):
    d = str(Path(temp_dir) / "myrepo")
    os.mkdir(d)
    return git_factory(d)


@pytest.fixture
def git_repo_with_remote(git_repo, temp_dir, call_git):
    d = str(Path(temp_dir) / "downstreamrepo")
    os.mkdir(d)

    # https://stackoverflow.com/a/3251126
    call_git("git config --bool core.bare true", cwd=git_repo.working_tree_dir)

    remote_name = "mylocalremote"
    local_git_repo = git_factory(d, remote_name=remote_name, remote=git_repo.git_dir)

    local_git_repo.remotes[remote_name].push(
        local_git_repo.active_branch.name, force=True
    )

    return dict(
        remote_name=remote_name, remote_git_repo=git_repo, git_repo=local_git_repo,
    )


@contextlib.contextmanager
def git_unbare_repo(working_tree_dir, call_git):
    call_git("git config --bool core.bare false", cwd=working_tree_dir)
    try:
        yield
    finally:
        call_git("git config --bool core.bare true", cwd=working_tree_dir)


def test_lockfile_created(git_repo):
    wd = git_repo.working_tree_dir
    lockfile = Path(wd) / ".synctogit.lockfile"

    tr = GitTransaction(git_repo)
    assert not lockfile.exists()

    with tr as t:
        assert tr is t
        assert lockfile.exists()

    assert not lockfile.exists()


def test_existing_lockfile_raises(git_repo):
    wd = git_repo.working_tree_dir
    lockfile = Path(wd) / ".synctogit.lockfile"
    lockfile.touch()

    tr = GitTransaction(git_repo)
    assert lockfile.exists()

    with pytest.raises(GitSimultaneousTransaction):
        with tr:
            pass

    assert lockfile.exists()


def test_dirty_changes_are_stashed(git_repo, call_git):
    wd = git_repo.working_tree_dir
    mystaged = Path(wd) / "mystaged"
    myunstaged = Path(wd) / "myunstaged"

    mystaged.write_text("deep below")
    call_git("git add mystaged", cwd=wd)
    myunstaged.write_text("in the upside down")

    with GitTransaction(git_repo):
        assert not mystaged.exists()
        assert not myunstaged.exists()
    assert not mystaged.exists()
    assert not myunstaged.exists()

    # Ensure no new commits have been created
    git_commits = call_git(r'git log --pretty=format:"%s" -n 2', cwd=wd)
    assert git_commits == initial_commit

    # And a single stash is created
    git_stashes = call_git("git stash list", cwd=wd)
    assert re.match(r"^stash@\{0\}[^\n]+$", git_stashes, flags=re.MULTILINE)

    git_stashed_staged_files = call_git(
        "git stash show -p stash@{0} --name-only", cwd=wd
    )
    assert git_stashed_staged_files == "mystaged"

    git_stashed_unstaged_files = (
        # The command below was crafted literally in blood and tears.
        call_git('git show stash@{0}^3 --pretty="" --name-only', cwd=wd)
    )
    assert git_stashed_unstaged_files == "myunstaged"


def test_changes_on_exception_are_stashed(git_repo, call_git):
    wd = git_repo.working_tree_dir
    myfile = Path(wd) / "myfile"

    with pytest.raises(ValueError):
        with GitTransaction(git_repo):
            myfile.write_text("that definitely was from *the* Stranger Things")
            raise ValueError("Some random exception")
    assert not myfile.exists()

    # Ensure no new commits have been created
    git_commits = call_git(r'git log --pretty=format:"%s" -n 2', cwd=wd)
    assert git_commits == initial_commit

    # And a single stash is created
    git_stashes = call_git("git stash list", cwd=wd)
    assert re.match(r"^stash@\{0\}[^\n]+$", git_stashes, flags=re.MULTILINE)

    git_stashed_staged_files = call_git(
        "git stash show -p stash@{0} --name-only", cwd=wd
    )
    assert git_stashed_staged_files == ""

    git_stashed_unstaged_files = (
        # The command below was crafted literally in blood and tears.
        call_git('git show stash@{0}^3 --pretty="" --name-only', cwd=wd)
    )
    assert git_stashed_unstaged_files == "myfile"


def test_remove_dirs_until_not_empty(git_repo):
    wd = git_repo.working_tree_dir
    d = Path(wd) / "a" / "b" / "c"
    f = Path(wd) / "a" / "file"

    with GitTransaction(git_repo) as t:
        os.makedirs(str(d))
        f.touch()
        assert d.exists()

        t.remove_dirs_until_not_empty(d)
        assert f.exists()
        assert not (Path(wd) / "a" / "b").exists()

        f.unlink()
        assert (Path(wd) / "a").exists()

        t.remove_dirs_until_not_empty(d)
        assert not (Path(wd) / "a").exists()
        assert Path(wd).exists()


@pytest.mark.parametrize(
    "push, commit_message",
    [
        # fmt: off
        (False, None),
        (False, "Мой коммитик-годовасик"),
        (True, None),
        # fmt: on
    ],
)
@patch(
    "synctogit.git_transaction._datetime_now",
    lambda: datetime.datetime(2018, 9, 25, 23, 30, 57),
)
def test_changes_are_committed(push, commit_message, git_repo_with_remote, call_git):
    git_repo = git_repo_with_remote["git_repo"]
    remote_git_repo = git_repo_with_remote["remote_git_repo"]
    remote_name = git_repo_with_remote["remote_name"]

    new_commit_message = commit_message or "Sync at 2018-09-25 23:30:57"

    wd = git_repo.working_tree_dir
    myfile = Path(wd) / "myfile"

    with GitTransaction(git_repo, push=push, remote_name=remote_name) as t:
        myfile.write_text("which is quite awesome")
        if commit_message:
            t.transaction_commit_message = commit_message

    assert myfile.exists()

    # Ensure that a new commit has been created
    git_commits = call_git(r'git log --pretty=format:"%s" -n 3', cwd=wd)
    assert git_commits == ("%s\n%s" % (new_commit_message, initial_commit))

    # Ensure that the working copy is clean
    git_status = call_git("git status --porcelain", cwd=wd)
    assert git_status == ""

    # Check commits in the remote repo
    git_remote_commits = call_git(
        r'git log --pretty=format:"%s" -n 3', cwd=remote_git_repo.working_tree_dir
    )
    if push:
        assert git_remote_commits == "%s\n%s" % (new_commit_message, initial_commit)
    else:
        assert git_remote_commits == initial_commit


def test_git_push_with_conflicts(git_repo_with_remote, call_git):
    git_repo = git_repo_with_remote["git_repo"]
    remote_git_repo = git_repo_with_remote["remote_git_repo"]
    remote_name = git_repo_with_remote["remote_name"]
    new_commit_message = "британец"

    with git_unbare_repo(remote_git_repo.working_tree_dir, call_git):
        call_git(
            'git commit --allow-empty -m "empty"', cwd=remote_git_repo.working_tree_dir
        )

    wd = git_repo.working_tree_dir
    myfile = Path(wd) / "myfile"

    with pytest.raises(GitPushError):
        with GitTransaction(git_repo, push=True, remote_name=remote_name) as t:
            t.transaction_commit_message = new_commit_message
            myfile.write_text("cats are the best, dont @ me")

    assert myfile.exists()

    # Ensure that a new commit has been created
    git_commits = call_git(r'git log --pretty=format:"%s" -n 3', cwd=wd)
    assert git_commits == "%s\n%s" % (new_commit_message, initial_commit)

    # Ensure that the working copy is clean
    git_status = call_git("git status --porcelain", cwd=wd)
    assert git_status == ""

    # Ensure that there're no new commits in the remote repo
    git_remote_commits = call_git(
        r'git log --pretty=format:"%s" -n 3', cwd=remote_git_repo.working_tree_dir
    )
    assert git_remote_commits == "empty\n%s" % initial_commit
