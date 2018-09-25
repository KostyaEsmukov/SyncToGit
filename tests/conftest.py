import os
import subprocess
import tempfile

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield os.path.realpath(tmpdirname)


@pytest.fixture
def call_git():
    def f(shell_command, *, cwd):
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
    return f
