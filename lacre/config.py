"""Lacre configuration

Routines defined here are responsible for processing configuration.
"""

from configparser import RawConfigParser

import os

import logging

# Environment variable name we read to retrieve configuration path.  This is to
# enable non-root users to set up and run GPG Mailgate and to make the software
# testable.
CONFIG_PATH_ENV = "GPG_MAILGATE_CONFIG"

# Global dict to keep configuration parameters.  It's hidden behind several
# utility functions to make it easy to replace it with ConfigParser object in
# the future.
cfg = dict()

def load_config() -> dict:
	"""Parses configuration file.

	If environment variable identified by CONFIG_PATH_ENV
	variable is set, its value is taken as a configuration file
	path.  Otherwise, the default is taken
	('/etc/gpg-mailgate.conf').
	"""
	configFile = os.getenv(CONFIG_PATH_ENV, '/etc/gpg-mailgate.conf')

	logging.debug(f"Loading configuration file: {configFile}")
	parser = read_config(configFile)

	global cfg
	cfg = copy_to_dict(parser)
	return cfg

def read_config(fileName) -> RawConfigParser:
	cp = RawConfigParser()
	cp.read(fileName)

	return cp

def copy_to_dict(confParser) -> dict:
	config = dict()

	for sect in confParser.sections():
		config[sect] = dict()
		for (name, value) in confParser.items(sect):
			config[sect][name] = value

	return config

def get_item(section, key):
	global cfg
	return cfg[section][key]

def has_section(section) -> bool:
	global cfg
	return section in cfg

def config_item_set(section, key) -> bool:
	global cfg
	return section in cfg and (key in cfg[section]) and not (cfg[section][key] is None)

def config_item_equals(section, key, value) -> bool:
	global cfg
	return section in cfg and key in cfg[section] and cfg[section][key] == value

def verbose_logging_enabled() -> bool:
	global cfg
	return config_item_equals("logging", "verbose", "yes")
