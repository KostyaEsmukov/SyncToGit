import datetime
from collections import OrderedDict
from pathlib import Path
from typing import Mapping, Tuple

import dateutil.parser
import pytz

from synctogit.filename_sanitizer import denormalize_filename
from synctogit.service.notes.stored_note import CorruptedNoteError, StoredNote

from .models import OneNotePage, OneNotePageId, OneNotePageMetadata


class OneNoteStoredNote(StoredNote):
    @classmethod
    def note_to_html(cls, note: OneNotePage, timezone: pytz.BaseTzInfo) -> bytes:
        note_header = OrderedDict()  # type: Mapping[str, str]

        for k in ["id", "title", "created", "last_modified"]:
            v = getattr(note.info, k)
            if k in ["created", "last_modified"]:
                v = str(v.astimezone(timezone))
            v = str(v)
            note_header[k] = v

        return super()._note_to_html(note_header=note_header, note_html=note.html)

    @classmethod
    def get_stored_note_metadata(
        cls, notes_dir, note_path: Path
    ) -> Tuple[OneNotePageId, OneNotePageMetadata]:
        dir_parts = note_path.relative_to(notes_dir).parents[0].parts
        if 2 != len(dir_parts):
            raise CorruptedNoteError(
                "Note's dir depth is expected to be exactly 2 levels", note_path
            )
        file = note_path.name

        header_vars = cls._parse_note_header(note_path)
        try:
            name = (
                # fmt: off
                tuple(denormalize_filename(d) for d in dir_parts)
                + (header_vars["title"],)
                # fmt: on
            )
            note_metadata = OneNotePageMetadata(
                dir=dir_parts,
                name=name,
                last_modified=cls._parse_datetime(header_vars["last_modified"]),
                file=file,
            )
            return header_vars["id"], note_metadata
        except (KeyError, ValueError) as e:
            raise CorruptedNoteError(
                "Unable to retrieve note metadata: %s" % repr(e), note_path
            )

    @classmethod
    def _parse_datetime(cls, dt: str) -> datetime.datetime:
        parsed_dt = dateutil.parser.parse(dt)
        if not parsed_dt.tzinfo:
            raise ValueError("Expected tz-aware datetime, received '%s'" % dt)
        return parsed_dt
