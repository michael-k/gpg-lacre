"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

import logging
import lacre
import lacre.config as conf
import sys
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope
import asyncio
import email
import time

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
import lacre.keycache as kcache


class MailEncryptionProxy:
    """A mail handler dispatching to appropriate mail operation."""

    def __init__(self, keys: kcache.KeyCache):
        """Initialise the mail proxy with a reference to the key cache."""
        self._keys = keys

    async def handle_DATA(self, server, session, envelope: Envelope):
        """Accept a message and either encrypt it or forward as-is."""
        start = time.process_time()
        try:
            message = email.message_from_bytes(envelope.content)
            for operation in gate.delivery_plan(envelope.rcpt_tos, self._keys):
                LOG.debug(f"Sending mail via {operation!r}")
                new_message = operation.perform(message)
                gate.send_msg(new_message, operation.recipients(), envelope.mail_from)
        except TypeError as te:
            LOG.exception("Got exception while processing", exc_info=te)
            return RESULT_ERROR

        ellapsed = time.process_time() - start
        LOG.info(f'Message delivered in {ellapsed} ms')
        return RESULT_OK


def _init_controller(keys: kcache.KeyCache, tout: float = 2.5):
    proxy = MailEncryptionProxy(keys)
    host, port = conf.daemon_params()
    LOG.info(f"Initialising a mail Controller at {host}:{port}")
    return Controller(proxy, hostname=host, port=port, ready_timeout=tout)


def _validate_config():
    missing = conf.validate_config()
    if missing:
        params = ", ".join([_full_param_name(tup) for tup in missing])
        LOG.error(f"Following mandatory parameters are missing: {params}")
        sys.exit(lacre.EX_CONFIG)


def _full_param_name(tup):
    return f"[{tup[0]}]{tup[1]}"


async def _sleep(minutes, heartbeat_func):
    while True:
        await asyncio.sleep(minutes * 60)
        heartbeat_func()


def _main():
    _validate_config()

    refresh_min = float(conf.get_item('gpg', 'cache_refresh_minutes', 2))

    keys = kcache.KeyCache(conf.get_item('gpg', 'keyhome'))
    keys.load()
    controller = _init_controller(keys)

    LOG.info("Starting the daemon...")
    controller.start()

    try:
        asyncio.run(_sleep(refresh_min, keys.load))
    except KeyboardInterrupt:
        LOG.info("Finishing...")

    controller.stop()

    LOG.info("Done")


if __name__ == '__main__':
    _main()
