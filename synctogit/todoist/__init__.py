import logging
import os
from pathlib import Path

from synctogit.config import Config
from synctogit.git_factory import gitignore_synctogit_files_prefix
from synctogit.git_transaction import GitTransaction
from synctogit.service import BaseAuth, BaseAuthSession, BaseSync, InvalidAuthSession

from .projects_renderer import ProjectsRenderer
from .todoist import Todoist
from .working_copy import TodoistWorkingCopy

logger = logging.getLogger(__name__)

__all__ = (
    "TodoistAuthSession",
    "TodoistAuth",
    "TodoistSync",
)


class TodoistAuthSession(BaseAuthSession):
    def __init__(self, token: str) -> None:
        self.token = token

    @classmethod
    def load_from_config(cls, config: Config) -> 'TodoistAuthSession':
        try:
            token = config.get_str('todoist', 'token')
        except ValueError:
            raise InvalidAuthSession('Todoist token is missing in config')

        return cls(token)

    def save_to_config(self, config: Config) -> None:
        config.set('todoist', 'token', self.token)

    def remove_session_from_config(self, config: Config) -> None:
        config.unset('todoist', 'token')


class TodoistAuth(BaseAuth[TodoistAuthSession]):
    @classmethod
    def interactive_auth(cls, config: Config) -> TodoistAuthSession:
        # XXX
        pass


class TodoistSync(BaseSync[TodoistAuthSession]):

    def run_sync(self) -> None:
        logger.info("Starting sync...")

        cache_dir = "%s.todoist" % gitignore_synctogit_files_prefix
        cache_path = Path(self.git.working_tree_dir) / cache_dir
        os.makedirs(str(cache_path), exist_ok=True)

        todoist = Todoist(str(cache_path), self.auth_session.token)

        git_conf = {
            'push': self.config.get_bool('git', 'push', False),
            'remote_name': self.config.get_str('git', 'remote_name', 'origin'),
        }

        with GitTransaction(self.git,
                            remote_name=git_conf["remote_name"],
                            push=git_conf["push"]) as t:
            todoist.sync()

            pr = ProjectsRenderer(
                projects=todoist.get_projects(),
                todo_items=todoist.get_todo_items()
            )
            wc = TodoistWorkingCopy(t, projects_renderer=pr)

            logger.info("Calculating changes...")
            changeset = wc.get_changes()

            logger.info("Applying changes...")
            wc.apply_changes(changeset)

            logger.info("Sync is complete!")
            logger.info("Closing the git transaction...")

        logger.info(
            "Changes: delete: %d, create: %d, update: %d, update index: %s",
            len(changeset.delete),
            len(changeset.new),
            len(changeset.update),
            changeset.index,
        )
        logger.info("Done")
