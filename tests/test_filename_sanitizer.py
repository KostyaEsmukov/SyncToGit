import pytest
from synctogit.filename_sanitizer import normalize_filename


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("раз два", "раз два"),
        ("раз_два", "раз__два"),
        ("00", "00"),
        ("\t", "__0009_"),
        ("con", "_con"),
        (r"раз/два\три", "раз_002fдва_005cтри"),
    ],
)
def test_normalize_filename(raw, expected):
    assert normalize_filename(raw) == expected
