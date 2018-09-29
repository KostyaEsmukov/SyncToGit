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
    def f(shell_command, *, cwd, space_trim=True):
        # NOTE! That shell_command must be compatible with Windows.
        # Have fun.

        try:
            p = subprocess.run(shell_command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               cwd=cwd,
                               shell=True, check=True, timeout=5)
            res = p.stdout.decode()
            if space_trim:
                res = res.strip()
            else:
                res = res.strip('\n')
            return res
        except subprocess.CalledProcessError as e:
            print(e.stdout.decode())
            raise
    return f
