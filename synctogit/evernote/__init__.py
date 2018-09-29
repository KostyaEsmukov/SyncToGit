import base64
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from synctogit import templates
from synctogit.config import Config
from synctogit.git_transaction import GitTransaction
from synctogit.service import BaseAuth, BaseAuthSession, BaseSync, InvalidAuthSession

from . import index_generator
from .auth import InteractiveAuth, UserCancelledError
from .evernote import Evernote
from .models import NoteGuid, NoteMetadata
from .working_copy import Changeset, EvernoteWorkingCopy

logger = logging.getLogger(__name__)

__all__ = (
    "EvernoteAuth",
    "EvernoteAuthSession",
    "EvernoteSync",
    "UserCancelledError",
)

# python -c "import base64; print base64.b64encode('123')"
_CONSUMER_KEY = 'kostya0shift-0653'
_CONSUMER_SECRET = base64.b64decode('M2EwMWJkYmJhNDVkYTYwMg==').decode()
_CALLBACK_URL = 'https://localhost:63543/non-existing-url'  # non existing link


class EvernoteAuthSession(BaseAuthSession):
    def __init__(self, token: str) -> None:
        self.token = token

    @classmethod
    def load_from_config(cls, config: Config) -> 'EvernoteAuthSession':
        try:
            encoded_token = config.get_str('evernote', 'token')
        except ValueError:
            raise InvalidAuthSession('Evernote token is missing in config')

        try:
            token = base64.b64decode(encoded_token).decode()
        except Exception:
            raise InvalidAuthSession('Evernote token is invalid')

        return cls(token)

    def save_to_config(self, config: Config) -> None:
        encoded_token = base64.b64encode(self.token.encode()).decode()
        config.set('evernote', 'token', encoded_token)

    def remove_session_from_config(self, config: Config) -> None:
        config.unset('evernote', 'token')


class EvernoteAuth(BaseAuth[EvernoteAuthSession]):
    @classmethod
    def interactive_auth(cls, config: Config) -> EvernoteAuthSession:
        token = InteractiveAuth(
            consumer_key=config.get_str(
                "evernote", "consumer_key", _CONSUMER_KEY
            ),
            consumer_secret=config.get_str(
                "evernote", "consumer_secret", _CONSUMER_SECRET
            ),
            callback_url=config.get_str(
                "evernote", "callback_url", _CALLBACK_URL
            ),
            sandbox=config.get_bool(
                'evernote', 'sandbox', False
            ),
        ).run()
        return EvernoteAuthSession(token)


class EvernoteSync(BaseSync[EvernoteAuthSession]):

    def run_sync(self) -> None:
        evernote = Evernote(
            sandbox=self.config.get_bool('evernote', 'sandbox', False),
        )
        evernote.auth(self.auth_session.token)
        self._sync_loop(evernote)

    def _sync_loop(self, evernote):
        git_conf = {
            'push': self.config.get_bool('git', 'push', False),
            'remote_name': self.config.get_str('git', 'remote_name', 'origin'),
        }

        any_fail = False
        is_converged = False
        while not is_converged:
            is_converged = True
            any_fail = False

            logger.info("Starting sync iteration...")

            with GitTransaction(self.git,
                                remote_name=git_conf["remote_name"],
                                push=git_conf["push"]) as t:
                wc = EvernoteWorkingCopy(t)

                logger.info("Retrieving actual metadata...")
                working_copy_metadata, evernote_metadata = (
                    self._retrieve_metadata(wc=wc, evernote=evernote)
                )

                logger.info("Calculating changes...")
                changeset = wc.calculate_changes(
                    working_copy_metadata=working_copy_metadata,
                    evernote_metadata=evernote_metadata,
                    force_update=self.force_full_resync,
                )

                logger.info("Applying changes...")
                wc.delete_notes(changeset.delete)
                update_context = self._update_notes(changeset, wc, evernote)

                is_converged = is_converged and update_context.is_converged

                logger.info("Updating index...")
                self._update_index(evernote_metadata)

                logger.info("Sync iteration is done!")
                logger.info("Closing the git transaction...")

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
            any_fail = len(update_context.failed_notes) != 0

        logger.info("Done")

        if any_fail:
            raise Exception("Sync done with fails")

    def _retrieve_metadata(self, *, wc: EvernoteWorkingCopy, evernote: Evernote):
        # Gather metadata from both Evernote and the git repo simultaneously.
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(wc.get_working_copy_metadata)
            b = pool.submit(evernote.get_actual_metadata)

            working_copy_metadata = a.result()
            evernote_metadata = b.result()
            return working_copy_metadata, evernote_metadata

    def _update_notes(
        self,
        changeset: Changeset,
        wc: EvernoteWorkingCopy,
        evernote: Evernote,
    ) -> '_UpdateContext':
        notes_to_update = [
            (guid, note_metadata)
            for op in ['new', 'update']
            for guid, note_metadata in getattr(changeset, op).items()
        ]
        update_context = _UpdateContext(total=len(notes_to_update))

        max_workers = self.config.get_int(
            "internals", "notes_download_threads", 30
        )

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            for guid, note_metadata in notes_to_update:
                pool.submit(self._update_note, guid, note_metadata,
                            update_context, wc, evernote)
        return update_context

    def _update_note(
        self,
        note_guid: NoteGuid,
        note_metadata: NoteMetadata,
        update_context: '_UpdateContext',
        wc: EvernoteWorkingCopy,
        evernote: Evernote,
    ) -> None:
        current = update_context.start()

        logger.info(
            "Getting note (%d/%d) contents: %s...",
            current, update_context.total, note_guid
        )

        try:
            note = evernote.get_note(
                note_guid,
                wc.get_relative_resources_url(note_guid, note_metadata)
            )
        except Exception as e:
            logger.warning(
                "Unable to get the note %s: %s", note_guid, repr(e)
            )
            update_context.add_failed(note_guid, note_metadata)
            return

        if note.update_sequence_num == note_metadata.update_sequence_num:
            logger.info(
                "Saving note (%d/%d) contents: %s...",
                current,
                update_context.total,
                note_guid,
            )
            wc.save_note(note, note_metadata)
            update_context.add_updated(note_guid, note_metadata)
        else:
            logger.info(
                "Skipping note (%d/%d) because it has changed "
                "during sync: %s...",
                current,
                update_context.total,
                note_guid,
            )
            update_context.set_not_converged()

    def _update_index(self, evernote_metadata) -> None:
        note_links = [
            index_generator.IndexLink(
                filesystem_path_parts=note.dir + (note.file,),
                name_parts=note.name,
            )
            for note in evernote_metadata.values()
        ]
        index_generator.generate(
            note_links,
            templates.file_writer(
                os.path.join(self.config.get_str('git', 'repo_dir'), "index.html")
            ),
        )


class _UpdateContext:
    def __init__(self, total: int):
        self.started = 0
        self.total = total
        self.updated_notes = []  # type: List[Tuple[NoteGuid, NoteMetadata]]
        self.failed_notes = []  # type: List[Tuple[NoteGuid, NoteMetadata]]
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

    def add_updated(self, note_guid, note_metadata):
        with self.lock:
            self.updated_notes.append((note_guid, note_metadata))

    def add_failed(self, note_guid, note_metadata):
        with self.lock:
            self.failed_notes.append((note_guid, note_metadata))
