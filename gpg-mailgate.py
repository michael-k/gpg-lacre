#!/usr/bin/python

#
#	gpg-mailgate
#
#	This file is part of the gpg-mailgate source code.
#
#	gpg-mailgate is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	gpg-mailgate source code is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

import email
import sys
import time
import logging

import lacre
import lacre.config as conf

start = time.time()
conf.load_config()
lacre.init_logging(conf.get_item('logging', 'config'))

# This has to be executed *after* logging initialisation.
import lacre.mailgate as mailgate

LOG = logging.getLogger(__name__)

missing_params = conf.validate_config()
if missing_params:
	LOG.error(f"Aborting delivery! Following mandatory config parameters are missing: {missing_params!r}")
	sys.exit(lacre.EX_CONFIG)

# Read e-mail from stdin
raw = sys.stdin.read()
raw_message = email.message_from_string( raw )
from_addr = raw_message['From']
to_addrs = sys.argv[1:]

# Let's start
mailgate.deliver_message(raw_message, from_addr, to_addrs)
(elapsed_s, process_t) = mailgate.exec_time_info(start)

LOG.info("Elapsed-time: {elapsed:.2f}s; Process-time: {process:.4f}s".format(elapsed=elapsed_s, process=process_t))
