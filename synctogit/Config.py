from __future__ import absolute_import

try:
    import configparser
except:
    import ConfigParser as configparser


class _NotSet(object):
    pass


class ConfigException(Exception):
    pass


class Config:
    def __init__(self, conffile):
        self.conffile = conffile

        self.conf = configparser.ConfigParser()
        with open(self.conffile, 'r') as f:
            self.conf.readfp(f)

    def _get(self, section, key, getter, default=_NotSet()):

        if not self.conf.has_section(section):
            if isinstance(default, _NotSet):
                raise ConfigException('Section %s is missing' % section)
            else:
                return default

        if not self.conf.has_option(section, key):
            if isinstance(default, _NotSet):
                raise ConfigException('Key %s from section %s is missing' % (key, section))
            else:
                v = default
        else:
            v = getter(section, key)

        return v

    def get_int(self, section, key, default=_NotSet()):
        v = self._get(section, key, self.conf.getint, default)
        return int(v)

    def get_string(self, section, key, default=_NotSet()):
        v = self._get(section, key, self.conf.get, default)
        return "" + v

    def get_boolean(self, section, key, default=_NotSet()):
        v = self._get(section, key, self.conf.getboolean, default)
        return bool(v)

    def _write(self):
        with open(self.conffile, 'w') as f:
            self.conf.write(f)

    def set(self, section, key, value):
        self.conf.set(section, key, value)
        self._write()

    def unset(self, section, key):
        self.conf.remove_option(section, key)
        self._write()
