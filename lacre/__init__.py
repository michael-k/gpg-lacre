"""Lacre --- the Postfix mail filter encrypting incoming email
"""

import logging
import logging.config

# Following structure configures logging iff a file-based configuration cannot
# be performed.  It only sets up a syslog handler, so that the admin has at
# least some basic information.
FAIL_OVER_LOGGING_CONFIG = {
	'version': 1,
	'formatters': {
		'sysfmt': {
			'format': '%(asctime)s %(module)s %(message)s',
			'datefmt': '%Y-%m-%d %H:%M:%S'
		},
	},
	'handlers': {
		'syslog': {
			'class': 'logging.handlers.SysLogHandler',
			'level': 'INFO',
			'formatter': 'sysfmt'
		}
	},
	'root': {
		'level': 'INFO',
		'handlers': ['syslog']
	}
}

def init_logging(config_filename):
	if config_filename is not None:
		logging.config.fileConfig(config_filename)
	else:
		logging.config.dictConfig(FAIL_OVER_LOGGING_CONFIG)
		logging.warning('Lacre logging configuration missing, using syslog as default')
