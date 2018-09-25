import pytest

from synctogit.filename_sanitizer import normalize_filename


@pytest.mark.parametrize(
    "raw, expected",
    [
        (" ", "_ _"),
        (".", "_."),
        ("..", "_.."),
        ("...", "_..."),
        (".my-not-hidden-file", "_.my-not-hidden-file"),
        ("00", "00"),
        ("\t", "__0009_"),
        ("con", "_con"),
        ("раз два", "раз два"),
        ("раз_два", "раз__два"),
        (r"раз/два\три", "раз_002fдва_005cтри"),
    ],
)
def test_normalize_filename(raw, expected):
    assert normalize_filename(raw) == expected


def test_empty_filename_raises():
    with pytest.raises(ValueError):
        normalize_filename(None)

    with pytest.raises(ValueError):
        normalize_filename("")
