from pathlib import Path
from typing import Sequence, Tuple

from synctogit.evernote.models import Note, NoteGuid, NoteMetadata
from synctogit.service.notes import Changeset, NoteResource, WorkingCopy

from .stored_note import EvernoteStoredNote


class EvernoteChangeset(Changeset[NoteGuid, NoteMetadata]):
    pass


class EvernoteWorkingCopy(WorkingCopy[NoteGuid, NoteMetadata, EvernoteChangeset]):
    # This class must be thread-safe

    changeset_cls = EvernoteChangeset

    @classmethod
    def _metadata_dir(cls, metadata: NoteMetadata) -> Sequence[str]:
        return metadata.dir

    @classmethod
    def _metadata_file(cls, metadata: NoteMetadata) -> str:
        return metadata.file

    @classmethod
    def _is_moved_note(cls, m1: NoteMetadata, m2: NoteMetadata) -> bool:
        return m1.name != m2.name

    @classmethod
    def _is_updated_note(cls, m1: NoteMetadata, m2: NoteMetadata) -> bool:
        return m1.update_sequence_num != m2.update_sequence_num

    def _get_stored_note_metadata(
        self, notes_dir, note_path: Path
    ) -> Tuple[NoteGuid, NoteMetadata]:
        return EvernoteStoredNote.get_stored_note_metadata(notes_dir, note_path)

    def save_note(self, note: Note, metadata: NoteMetadata):
        super()._save_note(
            note_key=note.guid,
            metadata=metadata,
            html_body=EvernoteStoredNote.note_to_html(note, self.timezone),
            resources=[
                NoteResource(filename=r.filename, body=r.body)
                for r in note.resources.values()
            ],
        )
