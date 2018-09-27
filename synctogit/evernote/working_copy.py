import concurrent.futures
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Mapping, NamedTuple, Sequence

from synctogit.evernote.models import Note, NoteGuid, NoteMetadata
from synctogit.git_transaction import GitTransaction, rmfile_silent

from .working_copy_note_parser import CorruptedNoteError, WorkingCopyNoteParser

logger = logging.getLogger(__name__)


def _seq_to_path(parts: Sequence[str]) -> Path:
    p = Path('')
    for part in parts:
        assert part not in ('.', '..')
        p = p / part
    return p


class EvernoteWorkingCopy:
    # This class must be thread-safe
    notes_dir_name = "Notes"
    resources_dir_name = "Resources"

    def __init__(self, git_transaction: GitTransaction) -> None:
        self.git_transaction = git_transaction
        self.repo_dir = git_transaction.repo_dir
        self.notes_dir = self.repo_dir / self.notes_dir_name
        self.resources_dir = self.repo_dir / self.resources_dir_name

    @classmethod
    def get_relative_resources_url(cls,
                                   noteguid: NoteGuid,
                                   metadata: NoteMetadata) -> str:
        """Returns a relative URL from a Note to its Resources directory.
        Intended to be used in the generated HTML pages of the notes.
        """
        ups = [".."] * (len(metadata.dir) + 1)
        path = [cls.resources_dir_name, noteguid, ""]
        return '/'.join(ups + path)

    @staticmethod
    def calculate_changes(
        *,
        evernote_metadata: Mapping[NoteGuid, NoteMetadata],
        working_copy_metadata: Mapping[NoteGuid, NoteMetadata],
        force_update: bool
    ) -> 'Changeset':
        changeset = Changeset(new={}, update={}, delete={})

        deleted_note_guids = set(working_copy_metadata.keys())

        for note_guid, note_metadata in evernote_metadata.items():
            if note_guid not in working_copy_metadata:
                changeset.new[note_guid] = note_metadata
            else:
                deleted_note_guids.discard(note_guid)
                old = working_copy_metadata[note_guid]
                new = note_metadata
                if old.name != new.name:
                    # Note has been renamed
                    changeset.delete[note_guid] = old
                    changeset.new[note_guid] = new
                elif (
                    force_update
                    or old.update_sequence_num != new.update_sequence_num
                ):
                    changeset.update[note_guid] = new

        changeset.delete.update({
            guid: working_copy_metadata[guid]
            for guid in deleted_note_guids
        })
        return changeset

    def save_note(self, note: Note, metadata: NoteMetadata):
        note_dir = self.notes_dir / _seq_to_path(metadata.dir)
        resources_dir = self.resources_dir / note.guid
        os.makedirs(str(note_dir), exist_ok=True)

        html_body = WorkingCopyNoteParser.note_to_html(note)
        note_path = note_dir / metadata.file
        note_path.write_bytes(html_body)

        if resources_dir.is_dir():
            shutil.rmtree(str(resources_dir))

        if note.resources:
            os.makedirs(str(resources_dir), exist_ok=True)

            for m in note.resources.values():
                resource_path = resources_dir / m.filename
                resource_path.write_bytes(m.body)

    def get_working_copy_metadata(
        self,
        worker_threads: int = 20,
    ) -> Mapping[NoteGuid, NoteMetadata]:
        note_metadata_futures = []

        with ThreadPoolExecutor(max_workers=worker_threads) as pool:
            for root, _, files in os.walk(str(self.notes_dir)):
                for fn in files:
                    _, ext = os.path.splitext(fn)
                    if ext != ".html":
                        # XXX delete it?
                        continue

                    note_path = Path(root) / fn
                    fut = pool.submit(
                        WorkingCopyNoteParser.get_stored_note_metadata,
                        self.notes_dir,
                        note_path,
                    )
                    note_metadata_futures.append((note_path, fut))

        return self._process_note_metadata_futures(note_metadata_futures)

    def _process_note_metadata_futures(
        self,
        note_metadata_futures: Sequence[concurrent.futures.Future],
    ) -> Mapping[NoteGuid, NoteMetadata]:
        note_guid_to_metadata = {}
        corrupted_note_guids = set()

        for note_path, note_metadata_future in note_metadata_futures:
            try:
                note_guid, note_metadata = note_metadata_future.result()
            except CorruptedNoteError as e:
                logger.warning("%s; removing corrupted note %s", str(e), note_path)
                self._delete_note(note_path)
            else:
                if note_guid in note_guid_to_metadata:
                    n1 = note_guid_to_metadata[note_guid]
                    n2 = note_metadata
                    logger.warning(
                        "Found two notes with the same GUIDs '%s', "
                        "removing both: %s and %s",
                        note_guid, n1, n2
                    )
                    self.delete_notes([n1, n2])
                    del note_guid_to_metadata[note_guid]
                    corrupted_note_guids.add(note_guid)
                elif note_guid in corrupted_note_guids:
                    logger.warning(
                        "Removing note with GUID '%s' as an another "
                        "conflict: %s",
                        note_guid, note_metadata
                    )
                    self.delete_notes([note_metadata])
                else:
                    note_guid_to_metadata[note_guid] = note_metadata

        self._delete_non_existing_resources(note_guid_to_metadata)
        return note_guid_to_metadata

    def _delete_non_existing_resources(
        self,
        metadata: Mapping[NoteGuid, NoteMetadata],
    ) -> None:
        try:
            root, dirs, _ = next(os.walk(str(self.resources_dir)))
        except StopIteration:
            # Resources dir doesn't exist -- no resources to delete, great.
            return

        for note_guid in dirs:
            if note_guid not in metadata:
                logger.warning(
                    "Resources for non-existing note %s "
                    "are going to be removed.", note_guid
                )
                shutil.rmtree(os.path.join(root, note_guid))

    def delete_notes(self, notes: Mapping[NoteGuid, NoteMetadata]) -> None:
        for note in notes.values():
            note_dir = self.notes_dir / _seq_to_path(note.dir)
            note_path = note_dir / note.file
            self._delete_note(note_path)

    def _delete_note(self, note_path: Path) -> None:
        rmfile_silent(note_path)
        note_dir = note_path.parents[0]
        # XXX Remove note's resources
        self.git_transaction.remove_dirs_until_not_empty(note_dir)


Changeset = NamedTuple(
    'Changeset',
    [
        ('new', Mapping[NoteGuid, NoteMetadata]),
        ('update', Mapping[NoteGuid, NoteMetadata]),
        ('delete', Mapping[NoteGuid, NoteMetadata]),
    ]
)
