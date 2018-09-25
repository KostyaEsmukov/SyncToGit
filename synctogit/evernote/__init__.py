import base64
import threading
import os
import logging

from synctogit.config import Config
from synctogit.service import InvalidAuthSession, BaseAuthSession, BaseAuth, BaseSync
from .auth import InteractiveAuth, UserCancelledError

from .evernote import Evernote
from ..git_transaction import GitTransaction
from .. import index_generator

logger = logging.getLogger(__name__)

__all__ = (
    "EvernoteAuth",
    "EvernoteAuthSession",
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
        self._god_sync(evernote)

    def _god_sync(self, evernote):
        git_conf = {
            'push': self.config.get_bool('git', 'push', False),
        }

        any_fail = False
        updates = [True]
        while updates[0]:
            updates[0] = False

            with GitTransaction(self.git,
                                push=git_conf["push"]) as t:
                logger.info("Calculating changes...")
                update = t.calculate_changes(
                    evernote.get_actual_metadata(), self.force_full_resync
                )
                logger.info("Applying changes...")

                t.delete_files(update['delete'])

                queue = []
                for op in ['new', 'update']:
                    for guid in update[op]:
                        queue.append([op, guid, update[op][guid]])

                total = len(queue)
                saved = [0]
                failed = [0]

                lock = threading.Lock()

                def job():
                    while True:
                        lock.acquire()
                        try:
                            j = queue.pop()
                            i = total - len(queue)
                        except Exception:
                            return
                        finally:
                            lock.release()

                        guid = j[1]
                        d = j[2]
                        logger.info(
                            "Getting note (%d/%d) contents: %s...", i, total, guid
                        )

                        try:
                            note = evernote.get_note(
                                guid, t.get_relative_resources_url(guid, d)
                            )
                        except Exception as e:
                            logger.warning(
                                "Unable to get the note %s: %s", guid, repr(e)
                            )
                            lock.acquire()
                            failed[0] += 1
                            lock.release()
                            continue

                        lock.acquire()
                        try:
                            saved[0] += 1
                            if note.update_sequence_num == d.update_sequence_num:
                                logger.info(
                                    "Saving note (%d/%d) contents: %s...",
                                    saved[0],
                                    total,
                                    guid,
                                )
                                t.save_note(note, d)
                            else:
                                logger.info(
                                    "Skipping note (%d/%d) because it has changed "
                                    "during sync: %s...",
                                    saved[0],
                                    total,
                                    guid,
                                )
                                updates[0] = True
                        finally:
                            lock.release()

                jobs = []
                for j in range(
                    self.config.get_int("internals", "notes_download_threads", 30)
                ):
                    jobs.append(threading.Thread(target=job))

                for j in jobs:
                    j.start()

                for j in jobs:
                    j.join()

                index_generator.generate(
                    update['result'],
                    index_generator.file_writer(
                        os.path.join(self.config.get_str('git', 'repo_dir'), "index.html")
                    ),
                )
                logger.info("Sync loop ended.")
                logger.info(
                    "Target was: delete: %d, create: %d, update: %d",
                    len(update['delete']),
                    len(update['new']),
                    len(update['update']),
                )
                logger.info("Result: saved: %d, failed: %d", saved[0], failed[0])
                any_fail = failed[0] != 0

        logger.info("Done")

        if any_fail:
            raise Exception("Sync done with fails")
