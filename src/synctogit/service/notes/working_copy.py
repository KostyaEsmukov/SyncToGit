import abc
import concurrent.futures
import logging
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Generic, Iterable, Mapping, NamedTuple, Sequence, Tuple, TypeVar

import pytz

from synctogit.git_transaction import GitTransaction, rmfile_silent

from .stored_note import CorruptedNoteError
from .types import TNoteKey, TNoteMetadata

logger = logging.getLogger(__name__)


def _seq_to_path(parts: Sequence[str]) -> Path:
    p = Path("")
    for part in parts:
        assert part not in (".", "..")
        p = p / part
    return p


NoteResource = NamedTuple(
    "NoteResource",
    [
        # fmt: off
        ("filename", str),
        ("body", bytes),
        # fmt: on
    ],
)


# TODO: replace with a dataclass
class Changeset(Generic[TNoteKey, TNoteMetadata]):
    def __init__(
        self,
        new: Mapping[TNoteKey, TNoteMetadata],
        update: Mapping[TNoteKey, TNoteMetadata],
        delete: Mapping[TNoteKey, TNoteMetadata],
    ) -> None:
        self.new = new
        self.update = update
        self.delete = delete

    def __repr__(self):
        return "%s(%s)" % (type(self).__name__, self.__dict__)

    def __eq__(self, other):
        if type(self) is not type(other):
            return False
        return (
            self.new == other.new
            and self.update == other.update
            and self.delete == other.delete
        )

    def __ne__(self, other):
        return not (self == other)


TChangeset = TypeVar("TChangeset", bound=Changeset)


class WorkingCopy(abc.ABC, Generic[TNoteKey, TNoteMetadata, TChangeset]):
    # This class must be thread-safe
    notes_dir_name = "Notes"
    resources_dir_name = "Resources"

    changeset_cls = Changeset

    def __init__(
        self, git_transaction: GitTransaction, timezone: pytz.BaseTzInfo
    ) -> None:
        self.git_transaction = git_transaction
        self.repo_dir = git_transaction.repo_dir
        self.notes_dir = self.repo_dir / self.notes_dir_name
        self.resources_dir = self.repo_dir / self.resources_dir_name
        self.timezone = timezone

    @classmethod
    @abc.abstractmethod
    def _metadata_dir(cls, metadata: TNoteMetadata) -> Sequence[str]:
        pass

    @classmethod
    @abc.abstractmethod
    def _metadata_file(cls, metadata: TNoteMetadata) -> str:
        pass

    @classmethod
    @abc.abstractmethod
    def _is_moved_note(cls, m1: TNoteMetadata, m2: TNoteMetadata) -> bool:
        pass

    @classmethod
    @abc.abstractmethod
    def _is_updated_note(cls, m1: TNoteMetadata, m2: TNoteMetadata) -> bool:
        pass

    @abc.abstractmethod
    def _get_stored_note_metadata(
        self, notes_dir, note_path: Path
    ) -> Tuple[TNoteKey, TNoteMetadata]:
        pass

    @classmethod
    def get_relative_resources_url(
        cls, note_key: TNoteKey, metadata: TNoteMetadata
    ) -> str:
        """Returns a relative URL from a Note to its Resources directory.
        Intended to be used in the generated HTML pages of the notes.
        """
        ups = [".."] * (len(cls._metadata_dir(metadata)) + 1)
        path = [cls.resources_dir_name, note_key, ""]
        return "/".join(ups + path)

    @classmethod
    def calculate_changes(
        cls,
        *,
        service_metadata: Mapping[TNoteKey, TNoteMetadata],
        working_copy_metadata: Mapping[TNoteKey, TNoteMetadata],
        force_update: bool
    ) -> TChangeset:
        changeset = cls.changeset_cls(new={}, update={}, delete={})

        deleted_note_keys = set(working_copy_metadata.keys())

        for note_key, note_metadata in service_metadata.items():
            if note_key not in working_copy_metadata:
                changeset.new[note_key] = note_metadata
            else:
                deleted_note_keys.discard(note_key)
                old = working_copy_metadata[note_key]
                new = note_metadata
                if cls._is_moved_note(old, new):
                    # Note has been renamed
                    changeset.delete[note_key] = old
                    changeset.new[note_key] = new
                elif force_update or cls._is_updated_note(old, new):
                    changeset.update[note_key] = new

        changeset.delete.update(
            {
                note_key: working_copy_metadata[note_key]
                for note_key in deleted_note_keys
            }
        )
        return changeset

    def _save_note(
        self,
        note_key: TNoteKey,
        metadata: TNoteMetadata,
        html_body: bytes,
        resources: Iterable[NoteResource],
    ):
        note_dir = self.notes_dir / _seq_to_path(self._metadata_dir(metadata))
        resources_dir = self.resources_dir / note_key
        os.makedirs(str(note_dir), exist_ok=True)

        note_path = note_dir / self._metadata_file(metadata)
        note_path.write_bytes(html_body)

        if resources_dir.is_dir():
            shutil.rmtree(str(resources_dir))

        if resources:
            os.makedirs(str(resources_dir), exist_ok=True)

            for m in resources:
                resource_path = resources_dir / m.filename
                resource_path.write_bytes(m.body)

    def get_working_copy_metadata(
        self, worker_threads: int = 20,
    ) -> Mapping[TNoteKey, TNoteMetadata]:
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
                        self._get_stored_note_metadata, self.notes_dir, note_path,
                    )
                    note_metadata_futures.append((note_path, fut))

        return self._process_note_metadata_futures(note_metadata_futures)

    def _process_note_metadata_futures(
        self, note_metadata_futures: Sequence[concurrent.futures.Future],
    ) -> Mapping[TNoteKey, TNoteMetadata]:
        note_key_to_metadata = {}
        corrupted_note_keys = set()

        for note_path, note_metadata_future in note_metadata_futures:
            try:
                note_key, note_metadata = note_metadata_future.result()
            except CorruptedNoteError as e:
                logger.warning("%s; removing corrupted note %s", str(e), note_path)
                self._delete_note(note_path)
            else:
                if note_key in note_key_to_metadata:
                    n1 = note_key_to_metadata[note_key]
                    n2 = note_metadata
                    logger.warning(
                        "Found two notes with the same keys '%s', "
                        "removing both: %s and %s",
                        note_key,
                        n1,
                        n2,
                    )
                    self.delete_notes([n1, n2])
                    del note_key_to_metadata[note_key]
                    corrupted_note_keys.add(note_key)
                elif note_key in corrupted_note_keys:
                    logger.warning(
                        "Removing note with key '%s' as an another conflict: %s",
                        note_key,
                        note_metadata,
                    )
                    self.delete_notes([note_metadata])
                else:
                    note_key_to_metadata[note_key] = note_metadata

        self._delete_non_existing_resources(note_key_to_metadata)
        return note_key_to_metadata

    def _delete_non_existing_resources(
        self, metadata: Mapping[TNoteKey, TNoteMetadata],
    ) -> None:
        try:
            root, dirs, _ = next(os.walk(str(self.resources_dir)))
        except StopIteration:
            # Resources dir doesn't exist -- no resources to delete, great.
            return

        for note_key in dirs:
            if note_key not in metadata:
                logger.warning(
                    "Resources for a non-existing note %s are going to be removed.",
                    note_key,
                )
                shutil.rmtree(os.path.join(root, note_key))

    def delete_notes(self, notes: Mapping[TNoteKey, TNoteMetadata]) -> None:
        for note in notes.values():
            note_dir = self.notes_dir / _seq_to_path(self._metadata_dir(note))
            note_path = note_dir / self._metadata_file(note)
            self._delete_note(note_path)

    def _delete_note(self, note_path: Path) -> None:
        rmfile_silent(note_path)
        note_dir = note_path.parents[0]
        # XXX Remove note's resources
        self.git_transaction.remove_dirs_until_not_empty(note_dir)
