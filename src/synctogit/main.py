import logging

import click

from . import __version__, evernote, git_config, onenote, todoist
from .config import Config, FilesystemConfigReadWriter
from .git_factory import git_factory
from .print_on_exception_only import PrintOnExceptionOnly
from .service import InvalidAuthSession, ServiceTokenExpiredError, UserCancelledError

logger = logging.getLogger(__name__)

services = {
    "evernote": evernote,
    "onenote": onenote,
    "todoist": todoist,
}


@click.command()
@click.version_option(version=__version__)
@click.option(
    "-b", "--batch", is_flag=True, help="Non-interactive mode",
)
@click.option(
    "-f", "--force-update", is_flag=True, help="Force download all notes",
)
@click.option(
    "-q",
    "--quiet",
    is_flag=True,
    help="Do not print anything unless exit code is non-zero",
)
@click.argument(
    "config", type=click.Path(exists=True),
)
@click.argument(
    "service", type=click.Choice(services.keys()),
)
def main(batch, force_update, quiet, config, service):
    """SyncToGit. Sync your Evernote notes to a local git repository.

    CONFIG should point to an existing config file. Note that this file
    might be overwritten by synctogit.
    """

    with PrintOnExceptionOnly(quiet, logging.INFO):
        synctogit(
            service=service, batch=batch, force_update=force_update, config=config,
        )


def synctogit(*, service, batch, force_update, config):
    config = Config(FilesystemConfigReadWriter(config))

    service_module = services[service]

    service_implementation = service_module.get_service_implementation()

    git = git_factory(
        repo_dir=git_config.git_repo_dir.get(config),
        branch=git_config.git_branch.get(config),
        remote_name=git_config.git_remote_name.get(config),
        remote=git_config.git_remote.get(config),
    )

    while _sync(service_implementation, git, config, batch, force_update):
        pass


def _sync(service_implementation, git, config, batch, force_update):
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
