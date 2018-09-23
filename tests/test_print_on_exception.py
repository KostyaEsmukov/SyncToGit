import pytest

from synctogit.main import logger
from synctogit.print_on_exception_only import PrintOnExceptionOnly

# TODO test logging as well
# The problem is that pytest mocks logging, so the logged data
# won't reach the handler installed in PrintOnExceptionOnly.


def test_quiet_success(capsys):
    with PrintOnExceptionOnly(quiet=True):
        print("hi")
        logger.warning("test")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_quiet_error(capsys):
    with pytest.raises(ValueError):
        with PrintOnExceptionOnly(quiet=True):
            print("hi")
            logger.warning("test")
            raise ValueError()

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "hi\n"


def test_non_quiet(capsys):
    with PrintOnExceptionOnly(quiet=False):
        print("hi")
        logger.warning("test")

        captured = capsys.readouterr()
        assert captured.out == "hi\n"
        assert captured.err == ""
