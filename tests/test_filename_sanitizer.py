import pytest

from synctogit.filename_sanitizer import (
    denormalize_filename,
    ext_from_mime_type,
    normalize_filename,
)
from synctogit.git_factory import gitignore_synctogit_files_prefix

raw_to_normalized = [
    (" ", "_0020"),
    (".", "_."),
    ("..", "_.."),
    ("...", "_..."),
    (".my-not-hidden-file", "_.my-not-hidden-file"),
    ("00", "00"),
    ("\t", "_0009"),
    ("\t_", "_0009__"),
    ("_0009_", "__0009__"),
    ("__0009_", "____0009__"),
    ("con", "_con"),
    ("con.txt", "_con.txt"),
    ("con.tar.gz", "_con.tar.gz"),
    ("contrib", "contrib"),
    ("раз два", "раз два"),
    ("раз_два", "раз__два"),
    (r"раз/два\три", "раз_002fдва_005cтри"),
    ("❤️and💩and👍🏾", "_2764_fe0fand_d83d_dca9and_d83d_dc4d_d83c_dffe"),
    (gitignore_synctogit_files_prefix, "_%s" % gitignore_synctogit_files_prefix),
]


@pytest.mark.parametrize(
    "raw, expected", raw_to_normalized,
)
def test_normalize_filename(raw, expected):
    assert normalize_filename(raw) == expected


def test_normalize_filename_with_disallowed_chars():
    # https://stackoverflow.com/a/62888
    chars = r'<>:"/\|?*\';,?'
    assert not (set(normalize_filename(chars)) & set(chars))


@pytest.mark.parametrize(
    "expected, raw", raw_to_normalized,
)
def test_denormalize_filename(raw, expected):
    assert denormalize_filename(raw) == expected


def test_empty_filename_raises():
    with pytest.raises(ValueError):
        normalize_filename(None)

    with pytest.raises(ValueError):
        normalize_filename("")

    with pytest.raises(ValueError):
        denormalize_filename(None)

    with pytest.raises(ValueError):
        denormalize_filename("")


@pytest.mark.parametrize("fn", ["a" * 251, "💩" * 26])
def test_long_filename_raises(fn):
    with pytest.raises(ValueError):
        normalize_filename(fn)


@pytest.mark.parametrize(
    "mime_type, expected_ext",
    [
        ("image/png", "png"),
        ("application/javascript", "js"),
        ("dsjkahdkas/uwqieyiquwe", "uwqieyiquwe"),
        ("text/plain", "txt"),
        ("application/msword", "doc"),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "docx",
        ),
    ],
)
def test_ext_from_mime_type(mime_type, expected_ext):
    assert expected_ext == ext_from_mime_type(mime_type)
