import datetime
from typing import Iterable, Mapping, NamedTuple, NewType, Optional, Sequence

NotebookGuid = NewType("NotebookGuid", str)
NoteGuid = NewType("NoteGuid", str)
TagGuid = NewType("TagGuid", str)


class NotebookInfo(NamedTuple):
    name: str
    update_sequence_num: int
    stack: Optional[str]


class NoteInfo(NamedTuple):
    title: str
    notebook_guid: NotebookGuid
    update_sequence_num: int
    tag_guids: Iterable[TagGuid]
    updated: datetime.datetime
    created: datetime.datetime
    deleted: datetime.datetime


class NoteMetadata(NamedTuple):
    dir: Sequence[str]
    file: str
    name: Sequence[str]
    update_sequence_num: int


class NoteResource(NamedTuple):
    body: bytes
    mime: str
    filename: str


class Note(NamedTuple):
    title: str
    update_sequence_num: int
    guid: NoteGuid
    updated: datetime.datetime
    created: datetime.datetime
    html: bytes
    resources: Mapping[str, NoteResource]
