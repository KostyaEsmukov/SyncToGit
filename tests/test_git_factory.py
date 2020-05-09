import os
from contextlib import ExitStack
from pathlib import Path

import pytest

from synctogit.git_factory import GitError, git_factory


def remotes_dump(remote_name, remote):
    # fmt: off
    return (
        "%(remote_name)s\t%(remote)s (fetch)\n"
        "%(remote_name)s\t%(remote)s (push)"
    ) % locals()
    # fmt: on


def test_git_missing_dir(temp_dir):
    d = str(Path(temp_dir) / "non-existing-dir")
    with pytest.raises(GitError):
        git_factory(d)


@pytest.mark.parametrize(
    "remote_name, remote",
    [
        # fmt: off
        ("origin", None),
        ("angel", "git@github.com:KostyaEsmukov/SyncToGit.git"),
        # fmt: on
    ],
)
def test_git_new_existing_empty_dir(call_git, temp_dir, remote_name, remote):
    branch = "spooky"
    d = str(Path(temp_dir) / "myrepo")
    os.mkdir(d)
    git_factory(d, branch=branch, remote_name=remote_name, remote=remote)

    git_root = call_git("git rev-parse --show-toplevel", cwd=d)
    assert git_root == d

    git_commits = call_git(r'git log --all --pretty=format:"%D %s" -n 2', cwd=d)
    assert git_commits == (
        "HEAD -> spooky Update .gitignore (automated commit by synctogit)"
    )

    git_branch = call_git("git symbolic-ref --short HEAD", cwd=d)
    assert git_branch == branch

    git_branches = call_git(
        "git for-each-ref --format='%(refname:short)' refs/heads/", cwd=d
    )
    assert git_branches == branch

    git_remotes = call_git("git remote -v", cwd=d)
    if remote:
        assert git_remotes == remotes_dump(remote_name, remote)
    else:
        assert git_remotes == ""


def test_git_new_existing_dirty_dir(temp_dir):
    p = Path(temp_dir) / "myrepo"
    d = str(p)
    os.mkdir(d)
    with open(str(p / "file"), "wt") as f:
        f.write("")

    with pytest.raises(GitError):  # Dirty dir
        git_factory(d)


def test_git_load_existing_empty(call_git, temp_dir):
    d = str(Path(temp_dir) / "myrepo")
    os.mkdir(d)
    call_git("git init", cwd=d)

    with pytest.raises(GitError):  # No initial commit
        git_factory(d)


@pytest.mark.parametrize(
    "remote_name, remote, shadow_remote",
    [
        ("origin", None, None),
        ("angel", "git@github.com:KostyaEsmukov/SyncToGit.git", None),
        ("angel", "git@github.com:new/remote.git", "git@github.com:old/remote.git"),
        ("angel", "git@github.com:same/remote.git", "git@github.com:same/remote.git"),
    ],
)
def test_git_load_existing_not_empty(
    call_git, temp_dir, remote_name, remote, shadow_remote
):
    p = Path(temp_dir) / "myrepo"
    d = str(p)
    os.mkdir(d)
    with open(str(p / "file"), "wt") as f:
        f.write("")
    call_git("git init", cwd=d)
    call_git("git add .", cwd=d)
    call_git('git commit -m "The Cake is a lie"', cwd=d)

    if shadow_remote:
        call_git("git remote add %s %s" % (remote_name, shadow_remote), cwd=d)

    with ExitStack() as stack:
        if shadow_remote and remote != shadow_remote:
            stack.enter_context(pytest.raises(GitError))
        git = git_factory(d, remote_name=remote_name, remote=remote)

    if shadow_remote and remote != shadow_remote:
        return

    assert git.head.commit.summary == (
        "Update .gitignore (automated commit by synctogit)"
    )
    assert git.head.commit.parents[0].summary == "The Cake is a lie"

    git_remotes = call_git("git remote -v", cwd=d)
    if remote:
        assert git_remotes == remotes_dump(remote_name, remote)
    else:
        assert git_remotes == ""

    with pytest.raises(GitError):
        git_factory(d, branch="some-other-branch")


def test_git_nested(call_git, temp_dir):
    root = Path(temp_dir) / "myroot"
    inner = root / "myinner"

    os.mkdir(str(root))
    call_git("git init", cwd=str(root))

    os.mkdir(str(inner))
    git_factory(str(inner))

    git_root = call_git("git rev-parse --show-toplevel", cwd=str(root))
    assert git_root == str(root)
    git_root = call_git("git rev-parse --show-toplevel", cwd=str(inner))
    assert git_root == str(inner)


@pytest.mark.parametrize("is_up_to_date", [False, True])
def test_gitignore_existing(call_git, temp_dir, is_up_to_date):
    p = Path(temp_dir) / "myrepo"
    d = str(p)
    os.mkdir(d)
    gitignore_file = p / ".gitignore"
    if is_up_to_date:
        gitignore_file.write_text(".synctogit*")
    else:
        gitignore_file.write_text("*.something")

    call_git("git init", cwd=d)
    call_git("git add .", cwd=d)
    call_git('git commit -m "The Cake is a lie"', cwd=d)

    git = git_factory(d)
    if is_up_to_date:
        assert git.head.commit.summary == "The Cake is a lie"
    else:
        assert git.head.commit.summary == (
            "Update .gitignore (automated commit by synctogit)"
        )
        assert git.head.commit.parents[0].summary == "The Cake is a lie"
        assert gitignore_file.read_text() == (
            # fmt: off
            "*.something\n"
            ".synctogit*\n"
            # fmt: on
        )


@pytest.mark.parametrize("dirty", ["repo", "gitignore"])
@pytest.mark.parametrize("is_dirty_staged", [False, True])
@pytest.mark.parametrize("is_new_file", [False, True])
def test_gitignore_update_with_dirty_repo(
    call_git, temp_dir, dirty, is_dirty_staged, is_new_file
):
    p = Path(temp_dir) / "myrepo"
    d = str(p)
    os.mkdir(d)
    gitignore_file = p / ".gitignore"

    if dirty == "gitignore":
        dirty_file = gitignore_file
    elif dirty == "repo":
        dirty_file = p / ".lalalala"

    call_git("git init", cwd=d)

    if not is_new_file:
        dirty_file.write_text("*.pdf")
        call_git("git add .", cwd=d)

    call_git('git commit --allow-empty -m "The Cake is a lie"', cwd=d)

    dirty_file.write_text("*.something")

    if is_dirty_staged:
        call_git("git add .", cwd=d)

    with ExitStack() as stack:
        if dirty == "gitignore":
            stack.enter_context(pytest.raises(GitError))
        git = git_factory(d)

    dirty_file.read_text() == "*.something"
    if dirty == "gitignore":
        # No commits should be created
        git_commits = call_git(r'git log --all --pretty=format:"%D %s" -n 2', cwd=d)
        assert git_commits == ("HEAD -> master The Cake is a lie")
    elif dirty == "repo":
        # Dirty changes should be there and still not be committed.
        gitignore_file.read_text() == ".synctogit*\n"
        assert git.head.commit.summary == (
            "Update .gitignore (automated commit by synctogit)"
        )
        assert git.head.commit.parents[0].summary == "The Cake is a lie"

        # Only .gitignore should be committed
        git_show = call_git('git show --pretty="" --name-only', cwd=d)
        assert git_show == ".gitignore"

    # Ensure that the dirty files are in the same staged/unstaged state
    git_status = call_git("git status --porcelain", cwd=d, space_trim=False)
    if is_new_file:
        prefix = "A  " if is_dirty_staged else "?? "
    else:
        prefix = "M  " if is_dirty_staged else " M "
    assert git_status.startswith(prefix)
