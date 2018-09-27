import datetime
from typing import Iterable, Mapping, NamedTuple, NewType, Optional, Sequence

NotebookGuid = NewType("NotebookGuid", str)
NoteGuid = NewType("NoteGuid", str)
TagGuid = NewType("TagGuid", str)


# Unfortunately Python 3.5 is not humane with regards to NamedTuples.

NotebookInfo = NamedTuple(
    "NotebookInfo",
    [
        ("name", str),
        ("update_sequence_num", int),
        ("stack", Optional[str]),
    ],
)


NoteInfo = NamedTuple(
    "NoteInfo",
    [
        ("title", str),
        ("notebook_guid", NotebookGuid),
        ("update_sequence_num", int),
        ("tag_guids", Iterable[TagGuid]),
        ("updated", datetime.datetime),
        ("created", datetime.datetime),
        ("deleted", datetime.datetime),
    ],
)


NoteMetadata = NamedTuple(
    "NoteMetadata",
    [
        ("dir", Sequence[str]),
        ("file", str),
        ("name", str),
        ("update_sequence_num", int),
    ],
)


NoteResource = NamedTuple(
    "NoteResource",
    [
        ("body", bytes),
        ("mime", str),
        ("filename", str),
    ]
)


Note = NamedTuple(
    "Note",
    [
        ("title", str),
        ("update_sequence_num", int),
        ("guid", NoteGuid),
        ("updated", datetime.datetime),
        ("created", datetime.datetime),
        ("html", bytes),
        ("resources", Mapping[str, NoteResource]),  # str -- resource hash
    ],
)
