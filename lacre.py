#!/usr/bin/python
#
# lacre
#
# This file is part of the lacre source code.
#
# lacre is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# lacre source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with lacre source code. If not, see <http://www.gnu.org/licenses/>.
#

import email
from email.policy import SMTPUTF8
import sys
import logging

import lacre
import lacre.config as conf
from lacre.stats import time_logger

conf.load_config()
lacre.init_logging(conf.get_item('logging', 'config'))

# This has to be executed *after* logging initialisation.
import lacre.core as core
from lacre.lazymessage import LazyMessage

LOG = logging.getLogger('lacre.py')

def main():
    with time_logger('Message delivery', LOG):
        missing_params = conf.validate_config()
        config_file = conf.config_source()

        if missing_params:
            LOG.error(f"Aborting delivery! Following mandatory config parameters are missing in {config_file!r}: {missing_params}")
            sys.exit(lacre.EX_CONFIG)

        delivered = False
        raw_message = None

        # Read recipients from the command-line
        to_addrs = sys.argv[1:]

        # Read e-mail from stdin, parse it
        raw = sys.stdin.read()
        raw_message = email.message_from_string(raw, policy=SMTPUTF8)
        from_addr = raw_message['From']

        lmessage = LazyMessage(to_addrs, lambda: raw_message)

        try:
            # Let's start
            core.deliver_message(raw_message, from_addr, to_addrs)
            delivered = True
        except:
            LOG.exception('Could not handle message')

        if not delivered:
            # It seems we weren't able to deliver the message.  In case it was
            # some silly message-encoding issue that shouldn't bounce the
            # message, we just try recoding the message body and delivering it.
            try:
                from_addr = raw_message['From']
                core.failover_delivery(raw_message, to_addrs, from_addr)
            except:
                LOG.exception('Failover delivery failed too')


if __name__ == '__main__':
    main()
