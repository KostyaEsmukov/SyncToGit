import base64
import logging
import os
import threading

import click

from . import index_generator
from .config import Config, FilesystemConfigReadWriter
from .evernote import Evernote, EvernoteTokenExpired
from .git import Git
from .print_on_exception_only import PrintOnExceptionOnly

# python -c "import base64; print base64.b64encode('123')"
_CONSUMER_KEY = 'kostya0shift-0653'
_CONSUMER_SECRET = base64.b64decode('M2EwMWJkYmJhNDVkYTYwMg==').decode()
_CALLBACK_URL = 'https://localhost:63543/non-existing-url'  # non existing link


@click.command()
@click.option(
    "-b",
    "--batch",
    is_flag=True,
    help='Non-interactive mode',
)
@click.option(
    "-f",
    "--force-update",
    is_flag=True,
    help='Force download all notes',
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help='Do not print anything unless exit code is non-zero',
)
@click.argument(
    'config',
    type=click.Path(exists=True),
)
def main(batch, force_update, quiet, config):
    """SyncToGit. Sync your Evernote notes to a local git repository.

    CONFIG should point to an existing config file. Note that this file
    might be overwritten by synctogit.
    """

    if quiet:
        with PrintOnExceptionOnly(logging.INFO):
            run(batch, force_update, config)
    else:
        logging.basicConfig(level=logging.INFO)
        run(batch, force_update, config)


def run(batch, force_update, config):
    config = Config(FilesystemConfigReadWriter(config))

    gc = {
        'repo_dir': config.get_str('git', 'repo_dir'),
        'branch': config.get_str('git', 'branch', 'master'),
        'push': config.get_bool('git', 'push', False),
    }
    git = Git(**gc)
    evernote = Evernote(config.get_bool('evernote', 'sandbox', False))

    while _sync(git, evernote, config, batch, force_update):
        pass


def _sync(git, evernote, config, batch, force_update):
    try:
        token = base64.b64decode(config.get_str('evernote', 'token')).decode()
    except Exception as e:
        logging.info("No valid token found.")
        if batch:
            raise Exception("Unable to proceed due to running batch mode.", e)

        c = {
            'consumer_key': config.get_str(
                "evernote", "consumer_key", _CONSUMER_KEY
            ),
            'consumer_secret': config.get_str(
                "evernote", "consumer_secret", _CONSUMER_SECRET
            ),
            'callback_url': config.get_str(
                "evernote", "callback_url", _CALLBACK_URL
            ),
        }
        token = evernote.retrieve_token(**c)
        config.set('evernote', 'token', base64.b64encode(token))

    try:
        logging.info("Authenticating...")
        evernote.auth(token)

        any_fail = False
        updates = [True]
        while updates[0]:
            updates[0] = False

            with git.transaction() as t:
                logging.info("Calculating changes...")
                update = t.calculate_changes(
                    evernote.get_actual_metadata(), force_update
                )
                logging.info("Applying changes...")

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
                        logging.info(
                            "Getting note (%d/%d) contents: %s...", i, total, guid
                        )

                        try:
                            note = evernote.get_note(
                                guid, t.get_relative_resources_url(guid, d)
                            )
                        except Exception as e:
                            logging.warning(
                                "Unable to get the note %s: %s", guid, repr(e)
                            )
                            lock.acquire()
                            failed[0] += 1
                            lock.release()
                            continue

                        lock.acquire()
                        try:
                            saved[0] += 1
                            if note['updateSequenceNum'] == d['updateSequenceNum']:
                                logging.info(
                                    "Saving note (%d/%d) contents: %s...",
                                    saved[0],
                                    total,
                                    guid,
                                )
                                t.save_note(note, d)
                            else:
                                logging.info(
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
                    config.get_int("internals", "notes_download_threads", 30)
                ):
                    jobs.append(threading.Thread(target=job))

                for j in jobs:
                    j.start()

                for j in jobs:
                    j.join()

                index_generator.generate(
                    update['result'],
                    os.path.join(config.get_str('git', 'repo_dir'), "index.html"),
                )
                logging.info("Sync loop ended.")
                logging.info(
                    "Target was: delete: %d, create: %d, update: %d",
                    len(update['delete']),
                    len(update['new']),
                    len(update['update']),
                )
                logging.info("Result: saved: %d, failed: %d", saved[0], failed[0])
                any_fail = failed[0] != 0

        logging.info("Done")

        if any_fail:
            raise Exception("Sync done with fails")

        return False
    except EvernoteTokenExpired:
        logging.warning("Auth token expired.")
        config.unset('evernote', 'token')
        return True


if __name__ == '__main__':
    main()
