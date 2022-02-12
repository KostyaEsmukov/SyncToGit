import datetime
from typing import Mapping, NamedTuple, NewType, Sequence

OneNoteSectionId = NewType("OneNoteSectionId", str)
OneNotePageId = NewType("OneNotePageId", str)


class OneNoteNotebook(NamedTuple):
    id: str
    name: str
    created: datetime.datetime
    last_modified: datetime.datetime
    is_default: bool
    sections: Sequence["OneNoteSection"]


class OneNoteSection(NamedTuple):
    id: OneNoteSectionId
    name: str
    created: datetime.datetime
    last_modified: datetime.datetime
    is_default: bool


class OneNotePageInfo(NamedTuple):
    id: OneNotePageId
    title: str
    created: datetime.datetime
    last_modified: datetime.datetime


class OneNotePageMetadata(NamedTuple):
    dir: Sequence[str]
    file: str
    name: Sequence[str]  # dir parts + note name
    last_modified: datetime.datetime


class OneNoteResource(NamedTuple):
    body: bytes
    mime: str
    filename: str


class OneNotePage(NamedTuple):
    info: OneNotePageInfo
    html: bytes
    resources: Mapping[str, OneNoteResource]  # str -- resource id
