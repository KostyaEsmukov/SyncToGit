import logging

import click

from . import evernote, todoist
from .config import Config, FilesystemConfigReadWriter
from .git_factory import git_factory
from .print_on_exception_only import PrintOnExceptionOnly
from .service import InvalidAuthSession, ServiceTokenExpiredError, UserCancelledError

logger = logging.getLogger(__name__)

services = {
    'evernote': evernote,
    'todoist': todoist,
}


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
@click.argument(
    'service',
    type=click.Choice(services.keys()),
)
def main(batch, force_update, quiet, config, service):
    """SyncToGit. Sync your Evernote notes to a local git repository.

    CONFIG should point to an existing config file. Note that this file
    might be overwritten by synctogit.
    """

    with PrintOnExceptionOnly(quiet, logging.INFO):
        run(service, batch, force_update, config)


def run(service, batch, force_update, config):
    config = Config(FilesystemConfigReadWriter(config))

    service_module = services[service]

    service_implementation = service_module.get_service_implementation()

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

    while _sync(service_implementation, git, gc, config, batch, force_update):
        pass


def _sync(service_implementation, git, git_conf, config, batch, force_update):
    AuthSession = service_implementation.auth_session
    Auth = service_implementation.auth
    Sync = service_implementation.sync

    try:
        session = AuthSession.load_from_config(config)
    except InvalidAuthSession as e:
        logger.info("Invalid auth session: %s", str(e))
        if batch:
            raise Exception("Unable to proceed due to running batch mode.", e)

        try:
            session = Auth.interactive_auth(config)
        except UserCancelledError as e:
            logger.info(str(e))
            return False
        session.save_to_config(config)

    try:
        logger.info("Authenticating...")
        sync = Sync(
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
