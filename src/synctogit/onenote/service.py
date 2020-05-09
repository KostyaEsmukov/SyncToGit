import base64
import json
import logging
from typing import Any, Dict, Mapping

from synctogit import templates
from synctogit.config import Config, IntConfigItem, StrConfigItem
from synctogit.git_config import git_push, git_remote_name
from synctogit.git_transaction import GitTransaction
from synctogit.service import BaseAuth, BaseAuthSession, BaseSync, InvalidAuthSession
from synctogit.service.notes import SyncIteration, WorkingCopy
from synctogit.timezone import get_timezone

from . import index_renderer
from .auth import InteractiveAuth
from .models import OneNotePage, OneNotePageId, OneNotePageMetadata
from .onenote import OneNoteClient
from .working_copy import OneNoteWorkingCopy

logger = logging.getLogger(__name__)


microsoft_graph_client_id = StrConfigItem(
    "microsoft_graph", "client_id", "4ea93786-4643-4b6c-89d5-5e2f53cc61d5"
)
microsoft_graph_client_secret = StrConfigItem(
    # python -c "import base64; print(base64.b64encode('123'.encode()).decode())"
    "microsoft_graph",
    "client_secret",
    base64.b64decode("eXRwWVZQSTU3OCEtZmJuaVJSSzUzXV8=").decode(),
)
microsoft_graph_redirect_uri = StrConfigItem(
    # A non-existing link.
    "microsoft_graph",
    "redirect_uri",
    "https://localhost:63543/non-existing-url",
)
microsoft_graph_oauth_scopes = StrConfigItem(
    "microsoft_graph",
    "oauth_scopes",
    "offline_access, User.Read, Notes.Read, Notes.Read.All",
)
microsoft_graph_token = StrConfigItem("microsoft_graph", "token")

# XXX dedup
notes_download_threads = IntConfigItem("internals", "notes_download_threads", 30)


class MicrosoftGraphAuthSession(BaseAuthSession):
    def __init__(self, token: Dict[str, Any]) -> None:
        self.token = token

    @classmethod
    def load_from_config(cls, config: Config) -> "MicrosoftGraphAuthSession":
        try:
            json_token = microsoft_graph_token.get(config)
        except (KeyError, ValueError):
            raise InvalidAuthSession("MicrosoftGraph token is missing in config")

        try:
            token = json.loads(json_token)
        except Exception:
            raise InvalidAuthSession("MicrosoftGraph token is not a valid json")

        return cls(token)

    def save_to_config(self, config: Config) -> None:
        microsoft_graph_token.set(config, json.dumps(self.token))

    def remove_session_from_config(self, config: Config) -> None:
        microsoft_graph_token.unset(config)

    def save_token_if_updated(self, config: Config, new_token) -> None:
        if self.token == new_token:
            return
        logger.info("Saving new auth token...")
        self.token = new_token
        self.save_to_config(config)


class MicrosoftGraphAuth(BaseAuth[MicrosoftGraphAuthSession]):
    @classmethod
    def interactive_auth(cls, config: Config) -> MicrosoftGraphAuthSession:
        token = InteractiveAuth(
            client_id=microsoft_graph_client_id.get(config),
            client_secret=microsoft_graph_client_secret.get(config),
            redirect_uri=microsoft_graph_redirect_uri.get(config),
            scopes=microsoft_graph_oauth_scopes.get(config),
        ).run()
        return MicrosoftGraphAuthSession(token)


class OneNoteSync(BaseSync[MicrosoftGraphAuthSession]):
    def run_sync(self) -> None:
        c = OneNoteClient(
            client_id=microsoft_graph_client_id.get(self.config),
            client_secret=microsoft_graph_client_secret.get(self.config),
            token=self.auth_session.token,
        )
        self._sync_loop(c)

    def _sync_loop(self, onenote: OneNoteClient):
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
                wc = OneNoteWorkingCopy(
                    git_transaction=t, timezone=get_timezone(self.config),
                )

                si = _OneNoteSyncIteration(
                    onenote=onenote,
                    working_copy=wc,
                    notes_download_threads=notes_download_threads.get(self.config),
                    force_full_resync=self.force_full_resync,
                    git_transaction=t,
                )

                changeset, update_context = si.run_transaction()
                self.auth_session.save_token_if_updated(self.config, onenote.token)

                logger.info("Sync iteration is done!")
                logger.info("Closing the git transaction...")

                is_converged = is_converged and update_context.is_converged

            _OneNoteSyncIteration.print_report(changeset, update_context)

            any_fail = len(update_context.failed_notes) != 0

        logger.info("Done")

        if any_fail:
            raise Exception("Sync done with fails")


class _OneNoteSyncIteration(
    SyncIteration[OneNotePageId, OneNotePageMetadata, OneNotePage]
):
    def __init__(
        self,
        *,
        onenote: OneNoteClient,
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
        self.onenote = onenote

    def get_note(
        self, note_key: OneNotePageId, note_metadata: OneNotePageMetadata
    ) -> OneNotePage:
        return self.onenote.get_page(
            note_key,
            self.working_copy.get_relative_resources_url(note_key, note_metadata),
        )

    def get_service_metadata(self) -> Mapping[OneNotePageId, OneNotePageMetadata]:
        self.onenote.sync_metadata()
        return self.onenote.metadata

    def is_same_note(
        self, note: OneNotePage, note_metadata: OneNotePageMetadata
    ) -> bool:
        return note.info.last_modified == note_metadata.last_modified

    def update_index(
        self,
        service_metadata: Mapping[OneNotePageId, OneNotePageMetadata],
        git_transaction: GitTransaction,
    ) -> None:
        index_renderer.render(
            notebooks=self.onenote.notebooks,
            pages=self.onenote.section_to_pages,
            service_metadata=service_metadata,
            write=templates.file_writer(
                str(self.git_transaction.repo_dir / "index.html")
            ),
        )
