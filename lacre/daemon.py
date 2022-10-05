"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

import logging
import lacre
import lacre.config as conf
import lacre.keycache as kcache
import sys
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope
import asyncio
import email

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

    def __init__(self, keys: kcache.KeyCache):
        """Initialise the mail proxy with a reference to the key cache."""
        self._keys = keys

    async def handle_DATA(self, server, session, envelope: Envelope):
        """Accept a message and either encrypt it or forward as-is."""
        try:
            message = email.message_from_bytes(envelope.content)
            for operation in gate.delivery_plan(envelope.rcpt_tos, self._keys):
                LOG.debug(f"Sending mail via {operation!r}")
                new_message = operation.perform(message)
                gate.send_msg(new_message, operation.recipients(), envelope.mail_from)
        except TypeError as te:
            LOG.exception("Got exception while processing", exc_info=te)
            return RESULT_ERROR

        return RESULT_NOT_IMPLEMENTED


def _init_controller(keys: kcache.KeyCache):
    proxy = MailEncryptionProxy(keys)
    host, port = conf.daemon_params()
    LOG.info(f"Initialising a mail Controller at {host}:{port}")
    return Controller(proxy, hostname=host, port=port)


def _validate_config():
    missing = conf.validate_config()
    if missing:
        params = ", ".join([_full_param_name(tup) for tup in missing])
        LOG.error(f"Following mandatory parameters are missing: {params}")
        sys.exit(lacre.EX_CONFIG)


def _full_param_name(tup):
    return f"[{tup[0]}]{tup[1]}"


async def _sleep():
    while True:
        await asyncio.sleep(5)


def _main():
    _validate_config()

    keys = kcache.KeyCache(conf.get_item('gpg', 'keyhome'))
    keys.load()
    controller = _init_controller(keys)

    LOG.info("Starting the daemon...")
    # starts the controller in a new thread
    controller.start()

    # _this_ thread now continues operation, so it may be used to control key
    # and certificate cache

    try:
        asyncio.run(_sleep())
    except KeyboardInterrupt:
        LOG.info("Finishing...")

    controller.stop()

    LOG.info("Done")


if __name__ == '__main__':
    _main()
