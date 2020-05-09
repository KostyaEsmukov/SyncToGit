import abc
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Generic, List, Mapping, Tuple

from synctogit.git_transaction import GitTransaction

from .types import TNote, TNoteKey, TNoteMetadata
from .working_copy import Changeset, WorkingCopy

logger = logging.getLogger(__name__)


class UpdateContext:
    def __init__(self, total: int):
        self.started = 0
        self.total = total
        self.updated_notes = []  # type: List[Tuple[TNoteKey, TNoteMetadata]]
        self.failed_notes = []  # type: List[Tuple[TNoteKey, TNoteMetadata]]
        self.is_converged = True
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            self.started += 1
            current = self.started
        return current

    def set_not_converged(self):
        with self.lock:
            self.is_converged = False

    def add_updated(self, note_key, note_metadata):
        with self.lock:
            self.updated_notes.append((note_key, note_metadata))

    def add_failed(self, note_key, note_metadata):
        with self.lock:
            self.failed_notes.append((note_key, note_metadata))


class SyncIteration(abc.ABC, Generic[TNoteKey, TNoteMetadata, TNote]):
    def __init__(
        self,
        *,
        working_copy: WorkingCopy,
        notes_download_threads: int,
        force_full_resync: bool,
        git_transaction: GitTransaction
    ) -> None:
        self.working_copy = working_copy
        self.notes_download_threads = notes_download_threads
        self.force_full_resync = force_full_resync
        self.git_transaction = git_transaction

    @abc.abstractmethod
    def get_note(self, note_key: TNoteKey, note_metadata: TNoteMetadata) -> TNote:
        pass

    @abc.abstractmethod
    def get_service_metadata(self) -> Mapping[TNoteKey, TNoteMetadata]:
        pass

    @abc.abstractmethod
    def is_same_note(self, note: TNote, note_metadata: TNoteMetadata) -> bool:
        pass

    @abc.abstractmethod
    def update_index(
        self,
        service_metadata: Mapping[TNoteKey, TNoteMetadata],
        git_transaction: GitTransaction,
    ) -> None:
        pass

    def run_transaction(self):
        logger.info("Retrieving actual metadata...")
        working_copy_metadata, service_metadata = self._retrieve_metadata()

        logger.info("Calculating changes...")
        changeset = self.working_copy.calculate_changes(
            working_copy_metadata=working_copy_metadata,
            service_metadata=service_metadata,
            force_update=self.force_full_resync,
        )

        logger.info("Applying changes...")
        self.working_copy.delete_notes(changeset.delete)
        update_context = self._update_notes(changeset)

        logger.info("Updating index...")
        self.update_index(service_metadata, self.git_transaction)

        return changeset, update_context

    @classmethod
    def print_report(cls, changeset, update_context):
        logger.info(
            "Target was: delete: %d, create: %d, update: %d",
            len(changeset.delete),
            len(changeset.new),
            len(changeset.update),
        )
        logger.info(
            "Result: saved: %d, failed: %d",
            len(update_context.updated_notes),
            len(update_context.failed_notes),
        )

    def _retrieve_metadata(self):
        # Gather metadata from both the service and the git repo simultaneously.
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(self.working_copy.get_working_copy_metadata)
            b = pool.submit(self.get_service_metadata)

            working_copy_metadata = a.result(timeout=3600)
            service_metadata = b.result(timeout=3600)
            return working_copy_metadata, service_metadata

    def _update_notes(self, changeset: Changeset) -> UpdateContext:
        notes_to_update = [
            (note_key, note_metadata)
            for op in ["new", "update"]
            for note_key, note_metadata in getattr(changeset, op).items()
        ]
        update_context = UpdateContext(total=len(notes_to_update))

        with ThreadPoolExecutor(max_workers=self.notes_download_threads) as pool:
            for note_key, note_metadata in notes_to_update:
                pool.submit(self._update_note, note_key, note_metadata, update_context)
        return update_context

    def _update_note(
        self,
        note_key: TNoteKey,
        note_metadata: TNoteMetadata,
        update_context: UpdateContext,
    ) -> None:
        current = update_context.start()

        logger.info(
            "Getting note (%d/%d) contents: %s...",
            current,
            update_context.total,
            note_key,
        )

        try:
            note = self.get_note(note_key, note_metadata)
        except Exception as e:
            logger.warning("Unable to get the note %s: %s", note_key, repr(e))
            update_context.add_failed(note_key, note_metadata)
            return

        if self.is_same_note(note, note_metadata):
            logger.info(
                "Saving note (%d/%d) contents: %s...",
                current,
                update_context.total,
                note_key,
            )
            try:
                self.working_copy.save_note(note, note_metadata)
                update_context.add_updated(note_key, note_metadata)
            except Exception:
                logger.info(
                    "Unable to save note (%d/%d) %s",
                    current,
                    update_context.total,
                    note_key,
                    exc_info=True,
                )
                update_context.add_failed(note_key, note_metadata)
                return
        else:
            logger.info(
                "Skipping note (%d/%d) because it has changed during sync: %s...",
                current,
                update_context.total,
                note_key,
            )
            update_context.set_not_converged()
