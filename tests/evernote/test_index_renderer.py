import io
from pathlib import Path
from typing import BinaryIO, Callable

from synctogit.evernote.index_renderer import IndexLink, render

data_path = Path(__file__).parents[0] / "data"


SAMPLE_NOTES = [
    IndexLink(
        filesystem_path_parts=(
            "Projects",
            "P - _0A (Й)",
            "жизнь.04d42576-e960-4184-aade-9798b1fe403f.html",
        ),
        name_parts=("Projects", "P - !Z (Щ) <>", "жизнь"),
    ),
    IndexLink(
        filesystem_path_parts=(
            "Learning",
            "Книги",
            "мои.b04b7672-f020-4203-ad1e-6c361c35c9ac.html",
        ),
        name_parts=("Learning", "Книги", "мои"),
    ),
    IndexLink(
        filesystem_path_parts=(
            "Learning",
            "Книги",
            "не мои.a5ccfd4c-1338-4b92-8339-16ff43390f10.html",
        ),
        name_parts=("Learning", "Книги", "не мои"),
    ),
]


def memory_writer(buf: BinaryIO) -> Callable[[bytes], None]:
    def write(data: bytes) -> None:
        buf.write(data)

    return write


def test_index_empty_notes():
    expected = (data_path / "index_renderer_empty.html").read_text()
    buf = io.BytesIO()
    render([], memory_writer(buf))
    assert buf.getvalue().decode() == expected


def test_index_sample_notes():
    expected = (data_path / "index_renderer_sample.html").read_text()
    buf = io.BytesIO()
    render(SAMPLE_NOTES, memory_writer(buf))
    assert buf.getvalue().decode() == expected
