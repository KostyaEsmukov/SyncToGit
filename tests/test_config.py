import contextlib
import io
from typing import ContextManager, TextIO

import pytest

from synctogit import config


class MemoryConfigReadWriter(config.ConfigReadWriter):
    def __init__(self, text: str) -> None:
        self.file = io.StringIO(text)

    @contextlib.contextmanager
    def reader(self) -> ContextManager[TextIO]:
        self.file.seek(0)
        yield self.file

    @contextlib.contextmanager
    def writer(self) -> ContextManager[TextIO]:
        self.file.seek(0)
        self.file.truncate(0)
        yield self.file

    def text(self) -> str:
        with self.reader() as f:
            return f.read()


def test_read_config():
    conf = """
[git]
repo_dir = git
push = false
num = 3

[evernote]
sandbox = true
token =
"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)

    assert config.StrConfigItem("git", "repo_dir").get(conf) == "git"
    assert config.BoolConfigItem("git", "push").get(conf) is False
    assert config.IntConfigItem("git", "num").get(conf) == 3

    assert config.BoolConfigItem("evernote", "sandbox").get(conf) is True
    assert config.StrConfigItem("evernote", "token").get(conf) == ""


def test_comments():
    conf = """
; large comment

[git]
; comment = 1

[evernote]
sandbox = true
; token = aaa

"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)

    evernote_sandbox = config.BoolConfigItem("evernote", "sandbox")
    git_comment = config.IntConfigItem("git", "comment")
    evernote_token = config.StrConfigItem("evernote", "token")

    assert evernote_sandbox.get(conf) is True
    with pytest.raises(KeyError):
        git_comment.get(conf)
    with pytest.raises(KeyError):
        evernote_token.get(conf)


def test_bool():
    conf = """
[git]
a = 1
b = true
c = True
d = yes

e = 0
f = false
g = False
h = no

i = None
"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)
    assert config.BoolConfigItem("git", "a").get(conf) is True
    assert config.BoolConfigItem("git", "b").get(conf) is True
    assert config.BoolConfigItem("git", "c").get(conf) is True
    assert config.BoolConfigItem("git", "d").get(conf) is True

    assert config.BoolConfigItem("git", "e").get(conf) is False
    assert config.BoolConfigItem("git", "f").get(conf) is False
    assert config.BoolConfigItem("git", "g").get(conf) is False
    assert config.BoolConfigItem("git", "h").get(conf) is False

    with pytest.raises(ValueError):
        assert config.BoolConfigItem("git", "i").get(conf) is False


def test_write():
    conf = """
[git]
repo_dir = git

push = false

[evernote]
; comment before sandbox
sandbox = true
; comment in the end
"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)

    evernote_token = config.StrConfigItem("evernote", "token")
    evernote_token.set(conf, "new-token")
    assert evernote_token.get(conf) == "new-token"

    # Unfortunately, configparser strips the comments :(
    assert (
        read_writer.text()
        == """
[git]
repo_dir = git

push = false

[evernote]
; comment before sandbox
sandbox = true
; comment in the end
token = new-token
"""
    )

    evernote_token.unset(conf)
    with pytest.raises(KeyError):
        evernote_token.get(conf)
    assert (
        read_writer.text()
        == """
[git]
repo_dir = git

push = false

[evernote]
; comment before sandbox
sandbox = true
; comment in the end
"""
    )

    config.IntConfigItem("newsect", "num").set(conf, 42)
    config.BoolConfigItem("newsect", "bool").set(conf, True)
    assert (
        read_writer.text()
        == """
[git]
repo_dir = git

push = false

[evernote]
; comment before sandbox
sandbox = true
; comment in the end
[newsect]
num = 42
bool = True
"""
    )


def test_defaults():
    conf = """
[git]
a = s
"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)

    with pytest.raises(KeyError):
        config.StrConfigItem("no", "b").get(conf)
    with pytest.raises(KeyError):
        config.StrConfigItem("git", "b").get(conf)
    with pytest.raises(KeyError):
        config.IntConfigItem("git", "b").get(conf)
    with pytest.raises(KeyError):
        config.BoolConfigItem("git", "b").get(conf)

    assert config.StrConfigItem("no", "b", "yeah").get(conf) == "yeah"
    assert config.StrConfigItem("git", "b", "a-ha").get(conf) == "a-ha"
    assert config.IntConfigItem("git", "b", 42).get(conf) == 42
    assert config.BoolConfigItem("git", "b", True).get(conf) is True
    assert config.StrConfigItem("git", "b", None).get(conf) is None


def test_isset():
    conf = """
[aa]
num = 5
s = hi
"""
    read_writer = MemoryConfigReadWriter(conf)
    conf = config.Config(read_writer)

    non_existing = config.IntConfigItem("bb", "cc")
    assert not non_existing.isset(conf)

    non_existing.set(conf, 6)
    assert non_existing.isset(conf)

    num = config.IntConfigItem("aa", "num")
    assert num.isset(conf)

    bad_num = config.IntConfigItem("aa", "s", 5)
    with pytest.raises(ValueError):
        bad_num.isset(conf)
