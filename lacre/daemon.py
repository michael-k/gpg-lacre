"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

import logging
import lacre
import lacre.config as conf
from aiosmtpd.controller import Controller

# Mail status constants.
#
# These are the only values that our mail handler is allowed to return.
RESULT_OK = '250 OK'
RESULT_ERROR = '500 Could not process your message'
RESULT_NOT_IMPLEMENTED = '500 Not implemented yet'

# Load configuration and init logging, in this order.  Only then can we load
# the last Lacre module, i.e. lacre.mailgate.
conf.load_config()
lacre.init_logging(conf.get_item("logging", "config"))
LOG = logging.getLogger(__name__)

import lacre.mailgate as gate


class MailEncryptionProxy:
    """A mail handler dispatching to appropriate mail operation."""

    async def handle_DATA(self, server, session, envelope):
        """Accept a message and either encrypt it or forward as-is."""
        # for now, just return an error because we're not ready to handle mail

        for r, s in gate.delivery_plan(envelope.rcpt_tos):
            print(r)

        return RESULT_NOT_IMPLEMENTED


def _init_controller():
    proxy = MailEncryptionProxy()
    host, port = conf.relay_params()
    return Controller(proxy, hostname=host, port=port)


def _main():
    controller = _init_controller()

    # starts the controller in a new thread
    controller.start()

    # _this_ thread now continues operation, so it may be used to control key
    # and certificate cache

    controller.stop()


if __name__ == '__main__':
    _main()
