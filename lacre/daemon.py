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
from watchdog.observers import Observer

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

import lacre.core as gate
import lacre.keyring as kcache


class MailEncryptionProxy:
    """A mail handler dispatching to appropriate mail operation."""

    def __init__(self, keyring: kcache.KeyRing):
        """Initialise the mail proxy with a reference to the key cache."""
        self._keyring = keyring

    async def handle_DATA(self, server, session, envelope: Envelope):
        """Accept a message and either encrypt it or forward as-is."""
        start = time.process_time()
        try:
            keys = await self._keyring.freeze_identities()
            message = email.message_from_bytes(envelope.content)
            for operation in gate.delivery_plan(envelope.rcpt_tos, keys):
                LOG.debug(f"Sending mail via {operation!r}")
                new_message = operation.perform(message)
                gate.send_msg(new_message, operation.recipients(), envelope.mail_from)
        except TypeError as te:
            LOG.exception("Got exception while processing", exc_info=te)
            return RESULT_ERROR

        ellapsed = (time.process_time() - start) * 1000
        LOG.info(f'Message delivered in {ellapsed:.2f} ms')
        return RESULT_OK


def _init_controller(keys: kcache.KeyRing, tout: float = 5):
    proxy = MailEncryptionProxy(keys)
    host, port = conf.daemon_params()
    LOG.info(f"Initialising a mail Controller at {host}:{port}")
    return Controller(proxy, hostname=host, port=port, ready_timeout=tout)


def _init_reloader(keyring_dir: str, reloader) -> kcache.KeyringModificationListener:
    listener = kcache.KeyringModificationListener(reloader)
    observer = Observer()
    observer.schedule(listener, keyring_dir, recursive=False)
    return observer


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
        await asyncio.sleep(360)


def _main():
    _validate_config()

    keyring_path = conf.get_item('gpg', 'keyhome')
    keyring = kcache.KeyRing(keyring_path)
    controller = _init_controller(keyring)
    reloader = _init_reloader(keyring_path, keyring)

    LOG.info(f'Watching keyring directory {keyring_path}...')
    reloader.start()

    LOG.info('Starting the daemon...')
    controller.start()

    try:
        asyncio.run(_sleep())
    except KeyboardInterrupt:
        LOG.info("Finishing...")
    finally:
        LOG.info('Shutting down keyring watcher and the daemon...')
        reloader.stop()
        reloader.join()
        controller.stop()

    LOG.info("Done")


if __name__ == '__main__':
    _main()
