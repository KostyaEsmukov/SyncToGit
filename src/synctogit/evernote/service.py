import base64
import logging
from typing import Mapping

from synctogit import templates
from synctogit.config import BoolConfigItem, Config, IntConfigItem, StrConfigItem
from synctogit.git_config import git_push, git_remote_name
from synctogit.git_transaction import GitTransaction
from synctogit.service import BaseAuth, BaseAuthSession, BaseSync, InvalidAuthSession
from synctogit.service.notes import SyncIteration, WorkingCopy
from synctogit.timezone import get_timezone

from . import index_renderer
from .auth import InteractiveAuth
from .evernote import Evernote
from .models import Note, NoteGuid, NoteMetadata
from .working_copy import EvernoteWorkingCopy

logger = logging.getLogger(__name__)

__all__ = (
    "EvernoteAuth",
    "EvernoteAuthSession",
    "EvernoteSync",
)

evernote_consumer_key = StrConfigItem("evernote", "consumer_key", "kostya0shift-0653")
evernote_consumer_secret = StrConfigItem(
    # python -c "import base64; print(base64.b64encode('123'.encode()).decode())"
    "evernote",
    "consumer_secret",
    base64.b64decode("M2EwMWJkYmJhNDVkYTYwMg==").decode(),
)
evernote_callback_url = StrConfigItem(
    # A non-existing link.
    "evernote",
    "callback_url",
    "https://localhost:63543/non-existing-url",
)
evernote_sandbox = BoolConfigItem("evernote", "sandbox", False)
evernote_token = StrConfigItem("evernote", "token")

notes_download_threads = IntConfigItem("internals", "notes_download_threads", 30)


class EvernoteAuthSession(BaseAuthSession):
    def __init__(self, token: str) -> None:
        self.token = token

    @classmethod
    def load_from_config(cls, config: Config) -> "EvernoteAuthSession":
        try:
            encoded_token = evernote_token.get(config)
        except (KeyError, ValueError):
            raise InvalidAuthSession("Evernote token is missing in config")

        try:
            token = base64.b64decode(encoded_token).decode()
        except Exception:
            raise InvalidAuthSession("Evernote token is invalid")

        return cls(token)

    def save_to_config(self, config: Config) -> None:
        encoded_token = base64.b64encode(self.token.encode()).decode()
        evernote_token.set(config, encoded_token)

    def remove_session_from_config(self, config: Config) -> None:
        evernote_token.unset(config)


class EvernoteAuth(BaseAuth[EvernoteAuthSession]):
    @classmethod
    def interactive_auth(cls, config: Config) -> EvernoteAuthSession:
        token = InteractiveAuth(
            consumer_key=evernote_consumer_key.get(config),
            consumer_secret=evernote_consumer_secret.get(config),
            callback_url=evernote_callback_url.get(config),
            sandbox=evernote_sandbox.get(config),
        ).run()
        return EvernoteAuthSession(token)


class EvernoteSync(BaseSync[EvernoteAuthSession]):
    def run_sync(self) -> None:
        evernote = Evernote(sandbox=evernote_sandbox.get(self.config))
        evernote.auth(self.auth_session.token)
        self._sync_loop(evernote)

    def _sync_loop(self, evernote):
        any_fail = False
        is_converged = False
        while not is_converged:
            is_converged = True
            any_fail = False

            logger.info("Starting sync iteration...")

            with GitTransaction(
                self.git,
                remote_name=git_remote_name.get(self.config),
                push=git_push.get(self.config),
            ) as t:
                wc = EvernoteWorkingCopy(
                    git_transaction=t, timezone=get_timezone(self.config),
                )

                si = _EvernoteSyncIteration(
                    evernote=evernote,
                    working_copy=wc,
                    notes_download_threads=notes_download_threads.get(self.config),
                    force_full_resync=self.force_full_resync,
                    git_transaction=t,
                )

                changeset, update_context = si.run_transaction()

                logger.info("Sync iteration is done!")
                logger.info("Closing the git transaction...")

                is_converged = is_converged and update_context.is_converged

            _EvernoteSyncIteration.print_report(changeset, update_context)

            any_fail = len(update_context.failed_notes) != 0

        logger.info("Done")

        if any_fail:
            raise Exception("Sync done with fails")


class _EvernoteSyncIteration(SyncIteration[NoteGuid, NoteMetadata, Note]):
    def __init__(
        self,
        *,
        evernote: Evernote,
        working_copy: WorkingCopy,
        notes_download_threads: int,
        force_full_resync: bool,
        git_transaction: GitTransaction
    ) -> None:
        super().__init__(
            working_copy=working_copy,
            notes_download_threads=notes_download_threads,
            force_full_resync=force_full_resync,
            git_transaction=git_transaction,
        )
        self.evernote = evernote

    def get_note(self, note_key: NoteGuid, note_metadata: NoteMetadata) -> Note:
        return self.evernote.get_note(
            note_key,
            self.working_copy.get_relative_resources_url(note_key, note_metadata),
        )

    def get_service_metadata(self) -> Mapping[NoteGuid, NoteMetadata]:
        return self.evernote.get_actual_metadata()

    def is_same_note(self, note: Note, note_metadata: NoteMetadata) -> bool:
        return note.update_sequence_num == note_metadata.update_sequence_num

    def update_index(
        self,
        service_metadata: Mapping[NoteGuid, NoteMetadata],
        git_transaction: GitTransaction,
    ) -> None:
        note_links = [
            index_renderer.IndexLink(
                filesystem_path_parts=note.dir + (note.file,), name_parts=note.name,
            )
            for note in service_metadata.values()
        ]
        index_renderer.render(
            note_links,
            templates.file_writer(str(git_transaction.repo_dir / "index.html")),
        )
