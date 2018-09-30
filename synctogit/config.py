import abc
import contextlib
from typing import ContextManager, TextIO, Union

from configupdater import ConfigUpdater

DEFAULT_SENTINEL = object()


class ConfigReadWriter(abc.ABC):
    @abc.abstractmethod
    def reader(self) -> ContextManager[TextIO]:
        pass

    @abc.abstractmethod
    def writer(self) -> ContextManager[TextIO]:
        pass


class FilesystemConfigReadWriter(ConfigReadWriter):  # pragma: no cover
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path

    @contextlib.contextmanager
    def reader(self) -> ContextManager[TextIO]:
        with open(self.config_path, 'rt') as f:
            yield f

    @contextlib.contextmanager
    def writer(self) -> ContextManager[TextIO]:
        with open(self.config_path, 'wt') as f:
            yield f


class Config:
    def __init__(self, config_read_writer: ConfigReadWriter) -> None:
        self.config_read_writer = config_read_writer
        self.conf = ConfigUpdater()
        with self.config_read_writer.reader() as f:
            self.conf.read_file(f)

    def _get(self, section, key, converter, default=DEFAULT_SENTINEL):

        if section not in self.conf:
            if default == DEFAULT_SENTINEL:
                raise ValueError('Section %s is missing' % section)
            else:
                value = default
        elif key not in self.conf[section]:
            if default == DEFAULT_SENTINEL:
                raise ValueError(
                    'Key %s from section %s is missing' % (key, section)
                )
            else:
                value = default
        else:
            value = self.conf[section][key].value

        if value is None:
            return value
        return converter(value)

    def get_int(self, section: str, key: str,
                default: int = DEFAULT_SENTINEL) -> int:
        v = self._get(section, key, int, default)

        return v

    def get_str(self, section: str, key: str,
                default: str = DEFAULT_SENTINEL) -> str:
        v = self._get(section, key, str, default)
        return v

    def get_bool(self, section: str, key: str,
                 default: bool = DEFAULT_SENTINEL) -> bool:
        v = self._get(section, key, self._convert_to_boolean, default)
        return v

    @staticmethod
    def _convert_to_boolean(value):
        BOOLEAN_STATES = {
            '1': True, 'yes': True, 'true': True, 'on': True,
            '0': False, 'no': False, 'false': False, 'off': False,
        }
        if value is True or value is False:
            return value
        if value.lower() not in BOOLEAN_STATES:
            raise ValueError('Not a boolean: %s' % value)
        return BOOLEAN_STATES[value.lower()]

    def _write(self):
        with self.config_read_writer.writer() as f:
            self.conf.write(f)

    def set(self, section: str, key: str, value: Union[str, bool, int]) -> None:
        value = str(value)
        if section not in self.conf:
            self.conf.add_section(section)
        self.conf[section][key] = value
        self._write()

    def unset(self, section: str, key: str) -> None:
        del self.conf[section][key]
        self._write()
