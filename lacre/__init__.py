"""Lacre --- the Postfix mail filter encrypting incoming email
"""

import logging

# Initialise logging infrastructure.
#
# This is going to be removed at some point of time, but is used at the moment
# because it's easy and keeps the rest of the code quite clean.

def init_logging(log_filename):
	logging.basicConfig(filename = log_filename,
						format = '%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s',
						datefmt = '%Y-%m-%d %H:%M:%S',
						level = logging.DEBUG)
	logging.info("Starting logs from lacre module...")
