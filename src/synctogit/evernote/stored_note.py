import re
from collections import OrderedDict
from pathlib import Path
from typing import Mapping, Tuple

import pytz

from synctogit.evernote.models import Note, NoteGuid, NoteMetadata
from synctogit.filename_sanitizer import denormalize_filename
from synctogit.service.notes.stored_note import CorruptedNoteError, StoredNote


class EvernoteStoredNote(StoredNote):
    @classmethod
    def note_to_html(cls, note: Note, timezone: pytz.BaseTzInfo) -> bytes:
        note_header = OrderedDict()  # type: Mapping[str, str]

        for k in ["guid", "updateSequenceNum", "title", "created", "updated"]:
            k_ = re.sub("([A-Z]+)", r"_\1", k).lower()
            v = getattr(note, k_)
            if k in ["created", "updated"]:
                v = str(v.astimezone(timezone))
            v = str(v)
            note_header[k] = v

        return super()._note_to_html(note_header=note_header, note_html=note.html)

    @classmethod
    def get_stored_note_metadata(
        cls, notes_dir, note_path: Path
    ) -> Tuple[NoteGuid, NoteMetadata]:
        dir_parts = note_path.relative_to(notes_dir).parents[0].parts
        if not (1 <= len(dir_parts) <= 2):
            raise CorruptedNoteError(
                "Note's dir depth is expected to be within 1 to 2 levels", note_path
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
            # `created` and `updated` datetimes might be naive, because
            # in synctogit 1.x they were being saved without timezone
            # (in the Evernote user's timezone).
            note_metadata = NoteMetadata(
                dir=dir_parts,
                name=name,
                update_sequence_num=int(header_vars["updateSequenceNum"]),
                file=file,
            )
            return header_vars["guid"].lower(), note_metadata
        except (KeyError, ValueError) as e:
            raise CorruptedNoteError(
                "Unable to retrieve note metadata: %s" % repr(e), note_path
            )
