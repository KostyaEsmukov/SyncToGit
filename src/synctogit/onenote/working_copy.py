from pathlib import Path
from typing import Sequence, Tuple

import pytz

from synctogit.service.notes import Changeset, NoteResource, WorkingCopy

from .models import OneNotePage, OneNotePageId, OneNotePageMetadata
from .stored_note import OneNoteStoredNote


class OneNoteChangeset(Changeset[OneNotePageId, OneNotePageMetadata]):
    pass


class OneNoteWorkingCopy(
    WorkingCopy[OneNotePageId, OneNotePageMetadata, OneNoteChangeset]
):
    # This class must be thread-safe

    changeset_cls = OneNoteChangeset

    @classmethod
    def _metadata_dir(cls, metadata: OneNotePageMetadata) -> Sequence[str]:
        return metadata.dir

    @classmethod
    def _metadata_file(cls, metadata: OneNotePageMetadata) -> str:
        return metadata.file

    @classmethod
    def _is_moved_note(cls, m1: OneNotePageMetadata, m2: OneNotePageMetadata) -> bool:
        return m1.name != m2.name

    @classmethod
    def _is_updated_note(cls, m1: OneNotePageMetadata, m2: OneNotePageMetadata) -> bool:
        dt1 = m1.last_modified.astimezone(pytz.utc)
        dt2 = m2.last_modified.astimezone(pytz.utc)
        return dt1 != dt2

    def _get_stored_note_metadata(
        self, notes_dir, note_path: Path
    ) -> Tuple[OneNotePageId, OneNotePageMetadata]:
        return OneNoteStoredNote.get_stored_note_metadata(notes_dir, note_path)

    def save_note(self, note: OneNotePage, metadata: OneNotePageMetadata):
        super()._save_note(
            note_key=note.info.id,
            metadata=metadata,
            html_body=OneNoteStoredNote.note_to_html(note, self.timezone),
            resources=[
                NoteResource(filename=r.filename, body=r.body)
                for r in note.resources.values()
            ],
        )
