import abc
from typing import Generic, Type, TypeVar

from .config import Config


class InvalidAuthSession(ValueError):
    pass


T = TypeVar('T', bound='BaseAuthSession')


class BaseAuthSession(abc.ABC):

    @classmethod
    @abc.abstractmethod
    def load_from_config(cls: Type[T], config: Config) -> T:
        pass

    @abc.abstractmethod
    def save_to_config(self, config: Config) -> None:
        pass


class BaseAuth(abc.ABC, Generic[T]):

    @classmethod
    @abc.abstractmethod
    def interactive_auth(cls, config: Config) -> T:
        pass
