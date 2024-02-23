"""Lacre configuration.

Routines defined here are responsible for processing and validating
configuration.
"""

from enum import Enum, auto
from configparser import RawConfigParser

import os


# Environment variable name we read to retrieve configuration path.  This is to
# enable non-root users to set up and run Lacre and to make the software
# testable.
CONFIG_PATH_ENV = "LACRE_CONFIG"

# List of mandatory configuration parameters.  Each item on this list should be
# a pair: a section name and a parameter name.
MANDATORY_CONFIG_ITEMS = [("relay", "host"),
                          ("relay", "port"),
                          ("daemon", "host"),
                          ("daemon", "port"),
                          ("gpg", "keyhome"),
                          ('database', 'enabled'),
                          ('database', 'url'),
                          ('database', 'pooling_mode')]

CRON_REQUIRED = [('cron', 'mail_templates')]

# Global dict to keep configuration parameters.  It's hidden behind several
# utility functions to make it easy to replace it with ConfigParser object in
# the future.
cfg = dict()


def load_config() -> dict:
    """Parse configuration file.

    If environment variable identified by CONFIG_PATH_ENV
    variable is set, its value is taken as a configuration file
    path.  Otherwise, the default is taken
    ('/etc/lacre.conf').
    """
    config_file = config_source()

    parser = _read_config(config_file)

    # XXX: Global variable.  It is a left-over from old GPG-Mailgate code.  We
    # should drop it and probably use ConfigParser instance where configuration
    # parameters are needed.
    global cfg
    cfg = _copy_to_dict(parser)
    return cfg


def config_source() -> str:
    """Return path of configuration file.

    Taken from LACRE_CONFIG environment variable, and if it's not
    set, defaults to /etc/lacre.conf."""
    return os.getenv(CONFIG_PATH_ENV, '/etc/lacre.conf')


def _read_config(fileName) -> RawConfigParser:
    cp = RawConfigParser()
    cp.read(fileName)

    return cp


def _copy_to_dict(confParser) -> dict:
    config = dict()

    for sect in confParser.sections():
        config[sect] = dict()
        for (name, value) in confParser.items(sect):
            config[sect][name] = value

    return config


def get_item(section, key, empty_value=None):
    global cfg
    if config_item_set(section, key):
        return cfg[section][key]
    else:
        return empty_value


def has_section(section) -> bool:
    return section in cfg


def config_item_set(section, key) -> bool:
    return section in cfg and (key in cfg[section]) and not (cfg[section][key] is None)


def config_item_equals(section, key, value) -> bool:
    return section in cfg and key in cfg[section] and cfg[section][key] == value


def flag_enabled(section, key) -> bool:
    return config_item_equals(section, key, 'yes')


def validate_config(*, additional=None):
    """Check if configuration is complete.

    Returns a list of missing parameters, so an empty list means
    configuration is complete.

    If 'additional' parameter is specified, it should be a list of
    tuples (section, param).
    """
    missing = []
    for (section, param) in MANDATORY_CONFIG_ITEMS:
        if not config_item_set(section, param):
            missing.append((section, param))
    if additional:
        for (section, param) in additional:
            if not config_item_set(section, param):
                missing.append((section, param))
    return missing


#
# High level access to configuration.
#

def relay_params():
    """Return a (HOST, PORT) tuple identifying the mail relay."""
    return (cfg["relay"]["host"], int(cfg["relay"]["port"]))


def daemon_params():
    """Return a (HOST, PORT) tuple to setup a server socket for Lacre daemon."""
    return (cfg["daemon"]["host"], int(cfg["daemon"]["port"]))


def strict_mode():
    """Check if Lacre is configured to support only a fixed list of keys."""
    return ("default" in cfg and cfg["default"]["enc_keymap_only"] == "yes")


class FromStrMixin:
    """Additional operations for configuration enums."""

    @classmethod
    def from_str(cls, name, *, required=False):
        if name is None:
            return None

        name = name.upper()

        if name in cls.__members__:
            return cls.__members__[name]

        if required:
            raise NameError('Unsupported or missing value')
        else:
            return None

    @classmethod
    def from_config(cls, section, key, *, required=False):
        param = get_item(section, key)
        return cls.from_str(param, required=required)


class PGPStyle(FromStrMixin, Enum):
    """PGP message structure: PGP/Inline or PGP/MIME."""
    MIME = auto()
    INLINE = auto()


class PoolingMode(FromStrMixin, Enum):
    """Database connection pool behaviour.

    - Optimistic - recycles connections.
    - Pessimistic - checks connection before usage.
    """
    OPTIMISTIC = auto()
    PESSIMISTIC = auto()
