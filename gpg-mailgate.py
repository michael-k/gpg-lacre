#!/usr/bin/python
#
# gpg-mailgate
#
# This file is part of the gpg-mailgate source code.
#
# gpg-mailgate is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gpg-mailgate source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

import email
from email.policy import SMTPUTF8
import sys
import time
import logging

import lacre
import lacre.config as conf

start = time.process_time()
conf.load_config()
lacre.init_logging(conf.get_item('logging', 'config'))

# This has to be executed *after* logging initialisation.
import lacre.core as core

LOG = logging.getLogger('gpg-mailgate.py')

missing_params = conf.validate_config()
if missing_params:
    LOG.error(f"Aborting delivery! Following mandatory config parameters are missing: {missing_params!r}")
    sys.exit(lacre.EX_CONFIG)

try:

    # Read e-mail from stdin, parse it
    raw = sys.stdin.read()
    raw_message = email.message_from_string(raw, policy=SMTPUTF8)
    from_addr = raw_message['From']
    # Read recipients from the command-line
    to_addrs = sys.argv[1:]

    # Let's start
    core.deliver_message(raw_message, from_addr, to_addrs)
    process_t = (time.process_time() - start) * 1000

    LOG.info("Message delivered in {process:.2f} ms".format(process=process_t))
except:
    LOG.exception('Could not handle message')
    core.failover_delivery(raw_message, to_addrs)
