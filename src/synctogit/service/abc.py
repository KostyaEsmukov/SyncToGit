import abc
from typing import Generic, NamedTuple, Type, TypeVar

import git

from synctogit.config import Config


class InvalidAuthSession(ValueError):
    pass


T = TypeVar("T", bound="BaseAuthSession")


class BaseAuthSession(abc.ABC):
    @classmethod
    @abc.abstractmethod
    def load_from_config(cls: Type[T], config: Config) -> T:
        pass

    @abc.abstractmethod
    def save_to_config(self, config: Config) -> None:
        pass

    @abc.abstractmethod
    def remove_session_from_config(self, config: Config) -> None:
        pass


class BaseAuth(abc.ABC, Generic[T]):
    @classmethod
    @abc.abstractmethod
    def interactive_auth(cls, config: Config) -> T:
        pass


class BaseSync(abc.ABC, Generic[T]):
    def __init__(
        self, config: Config, auth_session: T, git: git.Repo, force_full_resync: bool
    ) -> None:
        self.config = config
        self.auth_session = auth_session
        self.git = git
        self.force_full_resync = force_full_resync

    @abc.abstractmethod
    def run_sync(self) -> None:
        pass


ServiceImplementation = NamedTuple(
    "ServiceImplementation",
    [
        ("auth_session", Type[BaseAuthSession]),
        ("auth", Type[BaseAuth]),
        ("sync", Type[BaseSync]),
    ],
)
