import pytest

from synctogit.evernote.models import NoteMetadata
from synctogit.evernote.working_copy import EvernoteWorkingCopy


@pytest.mark.parametrize(
    "dir, url",
    [
        (
            ("Eleven", "Haircut"),
            "../../../Resources/eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7/",
        ),
        (
            # fmt: off
            ("Eleven",),
            "../../Resources/eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7/",
            # fmt: on
        ),
    ],
)
def test_relative_resources_url(dir, url):
    metadata = NoteMetadata(
        dir=dir, name="mark", update_sequence_num=123, file="s1.html"
    )
    got_url = EvernoteWorkingCopy.get_relative_resources_url(
        "eaaaaaae-1797-4b92-ad11-f3f6e7ada8d7", metadata
    )
    assert got_url == url
