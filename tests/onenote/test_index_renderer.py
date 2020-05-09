import datetime
import io
from pathlib import Path
from typing import BinaryIO, Callable

import pytz

from synctogit.onenote.index_renderer import render
from synctogit.onenote.models import (
    OneNoteNotebook,
    OneNotePageInfo,
    OneNotePageMetadata,
    OneNoteSection,
)

timezone = pytz.timezone("Europe/Moscow")
dt_tzaware = timezone.localize(datetime.datetime.now())

data_path = Path(__file__).parents[0] / "data"


SAMPLE_PAGES = dict(
    notebooks=[
        OneNoteNotebook(
            id="n1",
            name="Learning",
            created=dt_tzaware,
            last_modified=dt_tzaware,
            is_default=False,
            sections=[
                OneNoteSection(
                    id="s1",
                    name="Книги",
                    created=dt_tzaware,
                    last_modified=dt_tzaware,
                    is_default=False,
                )
            ],
        ),
        OneNoteNotebook(
            id="n2",
            name="Projects",
            created=dt_tzaware,
            last_modified=dt_tzaware,
            is_default=True,
            sections=[
                OneNoteSection(
                    id="s2",
                    name="P - !Z (Щ) <>",
                    created=dt_tzaware,
                    last_modified=dt_tzaware,
                    is_default=True,
                )
            ],
        ),
    ],
    pages={
        "s1": [
            OneNotePageInfo(
                id="0-111aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999",
                title="мои",
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
            OneNotePageInfo(
                id="0-222aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999",
                title="не мои",
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
        ],
        "s2": [
            OneNotePageInfo(
                id="0-333aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999",
                title="жизнь",
                created=dt_tzaware,
                last_modified=dt_tzaware,
            ),
        ],
    },
    service_metadata={
        "0-111aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999": OneNotePageMetadata(
            dir=("Learning", "Книги"),
            file="мои.0-111aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Learning", "Книги", "мои"),
            last_modified=dt_tzaware,
        ),
        "0-222aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999": OneNotePageMetadata(
            dir=("Learning", "Книги"),
            file="не мои.0-222aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Learning", "Книги", "не мои"),
            last_modified=dt_tzaware,
        ),
        "0-333aa99a9999999aaaaa99aaa999aaaa!1-AAAAAAAAAAAAAAA!999": OneNotePageMetadata(
            dir=("Projects", "P - _0A (Й)"),
            file="жизнь.0-333aa99a9999999aaaaa99aaa999aaaa_00211-AAAAAAAAAAAAAAA_0021999.html",  # noqa
            name=("Projects", "P - !Z (Щ) <>", "жизнь"),
            last_modified=dt_tzaware,
        ),
    },
)


def memory_writer(buf: BinaryIO) -> Callable[[bytes], None]:
    def write(data: bytes) -> None:
        buf.write(data)

    return write


def test_index_empty_pages():
    expected = (data_path / "index_renderer_empty.html").read_bytes()
    buf = io.BytesIO()
    render(notebooks=[], pages={}, service_metadata={}, write=memory_writer(buf))
    assert buf.getvalue() == expected


def test_index_sample_pages():
    expected = (data_path / "index_renderer_sample.html").read_bytes()
    buf = io.BytesIO()
    render(**SAMPLE_PAGES, write=memory_writer(buf))
    assert buf.getvalue() == expected
