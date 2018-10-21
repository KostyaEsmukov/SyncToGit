from pathlib import Path

import pytest

from synctogit.service.notes.stored_note import CorruptedNoteError, StoredNote


@pytest.fixture
def note_html():
    return (
        "<!doctype html>\n"
        "<!-- PLEASE DO NOT EDIT THIS FILE -->\n"
        "<!-- All changes you've done here will be stashed on next sync -->\n"
        "<!--+++++++++++++-->\n"
        "<!-- guid: eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7 -->\n"
        "<!-- updateSequenceNum: 12345 -->\n"
        "<!-- title: раз два три название -->\n"
        "<!-- created: 2018-07-11 18:10:40 -->\n"
        "<!-- updated: 2018-09-23 22:33:10 -->\n"
        "<!----------------->\n"
        "<html>\n"
        "<head>\n"
    ).encode()


@pytest.fixture
def note_header_vars():
    return {
        "created": "2018-07-11 18:10:40",
        "guid": "eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7",
        "title": "раз два три название",
        "updateSequenceNum": "12345",
        "updated": "2018-09-23 22:33:10",
    }


def test_parse_note_header_valid(temp_dir, note_html, note_header_vars):
    note = Path(temp_dir) / "test.html"
    note.write_bytes(note_html)

    metadata = StoredNote._parse_note_header(note)
    assert metadata == note_header_vars


@pytest.mark.parametrize(
    'note_html',
    [
        (
            # No start mark
            "<!doctype html>\n"
            "<!-- PLEASE DO NOT EDIT THIS FILE -->\n"
            "<!-- All changes you've done here will be stashed on next sync -->\n"
            "<!-- guid: eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7 -->\n"
            "<!-- updateSequenceNum: 12345 -->\n"
            "<!-- title: раз два три название -->\n"
            "<!-- created: 2018-07-11 18:10:40 -->\n"
            "<!-- updated: 2018-09-23 22:33:10 -->\n"
            "<!----------------->\n"
            "<html>\n"
            "<head>\n"
        ).encode(),
        (
            # No end mark
            "<!doctype html>\n"
            "<!-- PLEASE DO NOT EDIT THIS FILE -->\n"
            "<!-- All changes you've done here will be stashed on next sync -->\n"
            "<!--+++++++++++++-->\n"
            "<!-- guid: eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7 -->\n"
            "<!-- updateSequenceNum: 12345 -->\n"
            "<!-- title: раз два три название -->\n"
            "<!-- created: 2018-07-11 18:10:40 -->\n"
            "<!-- updated: 2018-09-23 22:33:10 -->\n"
        ).encode(),
        (
            # Non-var between the marks
            "<!doctype html>\n"
            "<!-- PLEASE DO NOT EDIT THIS FILE -->\n"
            "<!-- All changes you've done here will be stashed on next sync -->\n"
            "<!--+++++++++++++-->\n"
            "<!-- guid : eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7 -->\n"
            "<!----------------->\n"
            "<html>\n"
            "<head>\n"
        ).encode(),
    ]
)
def test_parse_note_header_invalid(temp_dir, note_html):
    note = Path(temp_dir) / "test.html"
    note.write_bytes(note_html)

    with pytest.raises(CorruptedNoteError):
        StoredNote._parse_note_header(note)


@pytest.mark.parametrize(
    'note_html, expected',
    [
        (
            (
                "<!doctype html>\n"
                "<!--+++++++++++++-->\n"
                "<!-- title: contains trailing space  -->\n"
                "<!----------------->\n"
                "<html>\n"
                "<head>\n"
            ).encode(),
            {
                'title': 'contains trailing space ',
            },
        ),
        (
            (
                "<!doctype html>\n"
                "<!--+++++++++++++-->\n"
                "<!-- snake_case: is good -->\n"
                "<!-- camelCase: is good as well -->\n"
                "<!----------------->\n"
                "<html>\n"
                "<head>\n"
            ).encode(),
            {
                'snake_case': 'is good',
                'camelCase': 'is good as well',
            },
        ),
    ]
)
def test_peculiar_valid_cases(temp_dir, note_html, expected):
    note = Path(temp_dir) / "test.html"
    note.write_bytes(note_html)

    assert expected == StoredNote._parse_note_header(note)
