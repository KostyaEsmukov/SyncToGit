import contextlib
import io
from typing import ContextManager, TextIO

import pytest

from synctogit.config import Config, ConfigReadWriter


class MemoryConfigReadWriter(ConfigReadWriter):
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
    config = Config(read_writer)
    assert config.get_str('git', 'repo_dir') == 'git'
    assert config.get_bool('git', 'push') is False
    assert config.get_int('git', 'num') == 3

    assert config.get_bool('evernote', 'sandbox') is True
    assert config.get_str('evernote', 'token') == ''


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
    config = Config(read_writer)

    assert config.get_bool('evernote', 'sandbox') is True
    with pytest.raises(ValueError):
        config.get_int('git', 'comment')
    with pytest.raises(ValueError):
        config.get_str('evernote', 'token')


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
    config = Config(read_writer)
    assert config.get_bool('git', 'a') is True
    assert config.get_bool('git', 'b') is True
    assert config.get_bool('git', 'c') is True
    assert config.get_bool('git', 'd') is True

    assert config.get_bool('git', 'e') is False
    assert config.get_bool('git', 'f') is False
    assert config.get_bool('git', 'g') is False
    assert config.get_bool('git', 'h') is False

    with pytest.raises(ValueError):
        assert config.get_bool('git', 'i') is False


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
    config = Config(read_writer)

    config.set('evernote', 'token', 'new-token')
    assert config.get_str('evernote', 'token') == 'new-token'

    # Unfortunately, configparser strips the comments :(
    assert read_writer.text() == """[git]
repo_dir = git
push = false

[evernote]
sandbox = true
token = new-token

"""

    config.unset('evernote', 'token')
    with pytest.raises(ValueError):
        config.get_str('evernote', 'token')
    assert read_writer.text() == """[git]
repo_dir = git
push = false

[evernote]
sandbox = true

"""

    config.set('newsect', 'num', 42)
    config.set('newsect', 'bool', True)
    assert read_writer.text() == """[git]
repo_dir = git
push = false

[evernote]
sandbox = true

[newsect]
num = 42
bool = True

"""


def test_defaults():
    conf = """
[git]
a = s
"""
    read_writer = MemoryConfigReadWriter(conf)
    config = Config(read_writer)

    with pytest.raises(ValueError):
        config.get_str('no', 'b')
    with pytest.raises(ValueError):
        config.get_str('git', 'b')
    with pytest.raises(ValueError):
        config.get_int('git', 'b')
    with pytest.raises(ValueError):
        config.get_bool('git', 'b')

    assert config.get_str('no', 'b', 'yeah') == 'yeah'
    assert config.get_str('git', 'b', 'a-ha') == 'a-ha'
    assert config.get_int('git', 'b', 42) == 42
    assert config.get_bool('git', 'b', True) is True
