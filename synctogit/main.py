import logging

import click

from .config import Config, FilesystemConfigReadWriter
from .evernote import EvernoteAuth, EvernoteAuthSession, EvernoteSync
from .git_factory import git_factory
from .print_on_exception_only import PrintOnExceptionOnly
from .service import InvalidAuthSession, ServiceTokenExpiredError, UserCancelledError

logger = logging.getLogger(__name__)


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

    with PrintOnExceptionOnly(quiet, logging.INFO):
        run(batch, force_update, config)


def run(batch, force_update, config):
    config = Config(FilesystemConfigReadWriter(config))

    gc = {
        'branch': config.get_str('git', 'branch', 'master'),
        'push': config.get_bool('git', 'push', False),
        'remote': config.get_str('git', 'remote', None) or None,
        'remote_name': config.get_str('git', 'remote_name', 'origin'),
        'repo_dir': config.get_str('git', 'repo_dir'),
    }
    git = git_factory(
        repo_dir=gc['repo_dir'],
        branch=gc['branch'],
        remote_name=gc['remote_name'],
        remote=gc['remote'],
    )

    while _sync(git, gc, config, batch, force_update):
        pass


def _sync(git, git_conf, config, batch, force_update):
    try:
        session = EvernoteAuthSession.load_from_config(config)
    except InvalidAuthSession as e:
        logger.info("Invalid auth session: %s", str(e))
        if batch:
            raise Exception("Unable to proceed due to running batch mode.", e)

        try:
            session = EvernoteAuth.interactive_auth(config)
        except UserCancelledError as e:
            logger.info(str(e))
            return False
        session.save_to_config(config)

    try:
        logger.info("Authenticating...")
        sync = EvernoteSync(
            config=config,
            auth_session=session,
            git=git,
            force_full_resync=force_update,
        )
        sync.run_sync()
        return False
    except ServiceTokenExpiredError:
        logger.warning("Auth token expired.")
        session.remove_session_from_config(config)
        return True


if __name__ == '__main__':
    main()
