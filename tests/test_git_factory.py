import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from synctogit.git_factory import GitError, git_factory


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield os.path.realpath(tmpdirname)


def call_git(shell_command, *, cwd):
    # NOTE! That shell_command must be compatible with Windows.
    # Have fun.

    try:
        p = subprocess.run(shell_command,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT,
                           cwd=cwd,
                           shell=True, check=True, timeout=5)
        return p.stdout.decode().strip()
    except subprocess.CalledProcessError as e:
        print(e.stdout.decode())
        raise


def remotes_dump(remote_name, remote):
    return (
        "%(remote_name)s\t%(remote)s (fetch)\n"
        "%(remote_name)s\t%(remote)s (push)"
    ) % locals()


def test_git_missing_dir(temp_dir):
    d = str(Path(temp_dir) / 'non-existing-dir')
    with pytest.raises(GitError):
        git_factory(d)


@pytest.mark.parametrize('remote_name, remote', [
    ('origin', None),
    ('angel', 'git@github.com:KostyaEsmukov/SyncToGit.git'),
])
def test_git_new_existing_empty_dir(temp_dir, remote_name, remote):
    branch = 'spooky'
    d = str(Path(temp_dir) / 'myrepo')
    os.mkdir(d)
    git_factory(d, branch=branch, remote_name=remote_name, remote=remote)

    git_root = call_git("git rev-parse --show-toplevel", cwd=d)
    assert git_root == d

    git_commits = call_git(r'git log --all --pretty=format:"%D %s" -n 2', cwd=d)
    assert git_commits == "HEAD -> spooky Initial commit"

    git_branch = call_git("git symbolic-ref --short HEAD", cwd=d)
    assert git_branch == branch

    git_branches = call_git(
        "git for-each-ref --format='%(refname:short)' refs/heads/",
        cwd=d
    )
    assert git_branches == branch

    git_remotes = call_git("git remote -v", cwd=d)
    if remote:
        assert git_remotes == remotes_dump(remote_name, remote)
    else:
        assert git_remotes == ""


def test_git_new_existing_dirty_dir(temp_dir):
    p = Path(temp_dir) / 'myrepo'
    d = str(p)
    os.mkdir(d)
    with open(str(p / 'file'), 'wt') as f:
        f.write('')

    with pytest.raises(GitError):  # Dirty dir
        git_factory(d)


def test_git_load_existing_empty(temp_dir):
    d = str(Path(temp_dir) / 'myrepo')
    os.mkdir(d)
    call_git('git init', cwd=d)

    with pytest.raises(GitError):  # No initial commit
        git_factory(d)


@pytest.mark.parametrize('remote_name, remote, shadow_remote', [
    ('origin', None, None),
    ('angel', 'git@github.com:KostyaEsmukov/SyncToGit.git', None),
    ('angel', 'git@github.com:new/remote.git', 'git@github.com:old/remote.git'),
    ('angel', 'git@github.com:same/remote.git', 'git@github.com:same/remote.git'),
])
def test_git_load_existing_not_empty(temp_dir, remote_name, remote,
                                     shadow_remote):
    p = Path(temp_dir) / 'myrepo'
    d = str(p)
    os.mkdir(d)
    with open(str(p / 'file'), 'wt') as f:
        f.write('')
    call_git('git init', cwd=d)
    call_git('git add .', cwd=d)
    call_git('git commit -m "The Cake is a lie"', cwd=d)

    if shadow_remote:
        call_git("git remote add %s %s" % (remote_name, shadow_remote), cwd=d)

    if shadow_remote and remote != shadow_remote:
        with pytest.raises(GitError):
            git = git_factory(d, remote_name=remote_name, remote=remote)
        return
    else:
        git = git_factory(d, remote_name=remote_name, remote=remote)

    assert git.head.commit.summary == "The Cake is a lie"

    git_remotes = call_git("git remote -v", cwd=d)
    if remote:
        assert git_remotes == remotes_dump(remote_name, remote)
    else:
        assert git_remotes == ""

    with pytest.raises(GitError):
        git_factory(d, branch='some-other-branch')


def test_git_nested(temp_dir):
    root = Path(temp_dir) / 'myroot'
    inner = root / 'myinner'

    os.mkdir(str(root))
    call_git('git init', cwd=str(root))

    os.mkdir(str(inner))
    git_factory(str(inner))

    git_root = call_git("git rev-parse --show-toplevel", cwd=str(root))
    assert git_root == str(root)
    git_root = call_git("git rev-parse --show-toplevel", cwd=str(inner))
    assert git_root == str(inner)
