import abc
import contextlib
from typing import ContextManager, Generic, TextIO, TypeVar

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
        with open(self.config_path, "rt") as f:
            yield f

    @contextlib.contextmanager
    def writer(self) -> ContextManager[TextIO]:
        with open(self.config_path, "wt") as f:
            yield f


T = TypeVar("T")


class ConfigItem(abc.ABC, Generic[T]):
    def __init__(self, section: str, key: str, default: T = DEFAULT_SENTINEL) -> None:
        self.section = section
        self.key = key
        self.default = default

    def get(self, config: "Config") -> T:
        return config._get(self.section, self.key, self._conv, self.default)

    def isset(self, config: "Config") -> bool:
        try:
            config._get(self.section, self.key, self._conv)
        except KeyError:
            return False
        else:
            return True

    def set(self, config: "Config", value: T) -> None:
        value = str(value)
        if self.section not in config.conf:
            config.conf.add_section(self.section)
        config.conf[self.section][self.key] = value
        config._write()

    def unset(self, config: "Config") -> None:
        del config.conf[self.section][self.key]
        config._write()

    @abc.abstractmethod
    def _conv(self, value: str) -> T:
        pass


class StrConfigItem(ConfigItem[str]):
    def _conv(self, value: str) -> str:
        return str(value)


class IntConfigItem(ConfigItem[int]):
    def _conv(self, value: str) -> int:
        return int(value)


class BoolConfigItem(ConfigItem[bool]):
    def _conv(self, value: str) -> bool:
        BOOLEAN_STATES = {
            # fmt: off
            "1": True, "yes": True, "true": True, "on": True,
            "0": False, "no": False, "false": False, "off": False,
            # fmt: on
        }
        if value.lower() not in BOOLEAN_STATES:
            raise ValueError("Not a boolean: %s" % value)
        return BOOLEAN_STATES[value.lower()]


class Config:
    def __init__(self, config_read_writer: ConfigReadWriter) -> None:
        self.config_read_writer = config_read_writer
        self.conf = ConfigUpdater()
        with self.config_read_writer.reader() as f:
            self.conf.read_file(f)

    def _get(self, section, key, converter, default=DEFAULT_SENTINEL):

        if section not in self.conf:
            if default == DEFAULT_SENTINEL:
                raise KeyError("Section %s is missing" % section)
            else:
                value = default
        elif key not in self.conf[section]:
            if default == DEFAULT_SENTINEL:
                raise KeyError("Key %s from section %s is missing" % (key, section))
            else:
                value = default
        else:
            value = self.conf[section][key].value

        if value is default:
            return value
        return converter(value)

    def _write(self):
        with self.config_read_writer.writer() as f:
            self.conf.write(f)
