import datetime
from typing import Mapping, NamedTuple, NewType, Sequence

OneNoteSectionId = NewType("OneNoteSectionId", str)
OneNotePageId = NewType("OneNotePageId", str)


OneNoteNotebook = NamedTuple(
    "OneNoteNotebook",
    [
        ("id", str),
        ("name", str),
        ("created", datetime.datetime),
        ("last_modified", datetime.datetime),
        ("is_default", bool),
        ("sections", Sequence["OneNoteSection"]),
    ],
)

OneNoteSection = NamedTuple(
    "OneNoteSection",
    [
        ("id", OneNoteSectionId),
        ("name", str),
        ("created", datetime.datetime),
        ("last_modified", datetime.datetime),
        ("is_default", bool),
    ],
)

OneNotePageInfo = NamedTuple(
    "OneNotePageInfo",
    [
        ("id", OneNotePageId),
        ("title", str),
        ("created", datetime.datetime),
        ("last_modified", datetime.datetime),
    ],
)

OneNotePageMetadata = NamedTuple(
    "OneNotePageMetadata",
    [
        ("dir", Sequence[str]),
        ("file", str),
        ("name", Sequence[str]),  # dir parts + note name
        ("last_modified", datetime.datetime),
    ],
)

OneNoteResource = NamedTuple(
    "OneNoteResource",
    [
        # fmt: off
        ("body", bytes),
        ("mime", str),
        ("filename", str),
        # fmt: on
    ],
)

OneNotePage = NamedTuple(
    "OneNotePage",
    [
        ("info", OneNotePageInfo),
        ("html", bytes),
        ("resources", Mapping[str, OneNoteResource]),  # str -- resource id
    ],
)
