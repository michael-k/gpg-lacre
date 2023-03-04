"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

import logging
import lacre
from lacre.text import DOUBLE_EOL_BYTES
import lacre.config as conf
import sys
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope
import asyncio
import email
from email.policy import SMTPUTF8
import time
from watchdog.observers import Observer

# Mail status constants.
#
# These are the only values that our mail handler is allowed to return.
RESULT_OK = '250 OK'
RESULT_ERROR = '500 Could not process your message'

# Load configuration and init logging, in this order.  Only then can we load
# the last Lacre module, i.e. lacre.mailgate.
conf.load_config()
lacre.init_logging(conf.get_item("logging", "config"))
LOG = logging.getLogger('lacre.daemon')

from GnuPG import EncryptionException
import lacre.core as gate
import lacre.keyring as kcache
from lacre.mailop import KeepIntact


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
            LOG.debug('Parsing message: %s', self._beginning(envelope))
            message = email.message_from_bytes(envelope.original_content, policy=SMTPUTF8)
            LOG.debug('Parsed into %s: %s', type(message), repr(message))

            if message.defects:
                # Sometimes a weird message cannot be encoded back and
                # delivered, so before bouncing such messages we at least
                # record information about the issues.  Defects are identified
                # by email.* package.
                LOG.warning("Issues found: %d; %s", len(message.defects), repr(message.defects))

            if conf.flag_enabled('daemon', 'log_headers'):
                LOG.info('Message headers: %s', self._extract_headers(message))

            for operation in gate.delivery_plan(envelope.rcpt_tos, message, keys):
                LOG.debug(f"Sending mail via {operation!r}")
                try:
                    new_message = operation.perform(message)
                    gate.send_msg_bytes(new_message, operation.recipients(), envelope.mail_from)
                except EncryptionException:
                    # If the message can't be encrypted, deliver cleartext.
                    LOG.exception('Unable to encrypt message, delivering in cleartext')
                    if not isinstance(operation, KeepIntact):
                        self._send_unencrypted(operation, message, envelope)
                    else:
                        LOG.error(f'Cannot perform {operation}')

        except:
            LOG.exception('Unexpected exception caught, bouncing message')
            return RESULT_ERROR

        ellapsed = (time.process_time() - start) * 1000
        LOG.info(f'Message delivered in {ellapsed:.2f} ms')

        return RESULT_OK

    def _send_unencrypted(self, operation, message, envelope):
        keep = KeepIntact(operation.recipients())
        new_message = keep.perform(message)
        gate.send_msg_bytes(new_message, operation.recipients(), envelope.mail_from)

    def _beginning(self, e: Envelope) -> bytes:
        double_eol_pos = e.original_content.find(DOUBLE_EOL_BYTES)
        if double_eol_pos < 0:
            limit = len(e.original_content)
        else:
            limit = double_eol_pos
        end = min(limit, 2560)
        return e.original_content[0:end]

    def _extract_headers(self, message: email.message.Message):
        return {
            'mime'     : message.get_content_type(),
            'charsets' : message.get_charsets(),
            'cte'      : message['Content-Transfer-Encoding']
            }


def _init_controller(keys: kcache.KeyRing, max_body_bytes=None, tout: float = 5):
    proxy = MailEncryptionProxy(keys)
    host, port = conf.daemon_params()
    LOG.info(f"Initialising a mail Controller at {host}:{port}")
    return Controller(proxy, hostname=host, port=port,
                      ready_timeout=tout,
                      data_size_limit=max_body_bytes)


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
    max_data_bytes = int(conf.get_item('daemon', 'max_data_bytes', 2**25))

    loop = asyncio.get_event_loop()

    keyring = kcache.KeyRing(keyring_path, loop)
    controller = _init_controller(keyring, max_data_bytes)
    reloader = _init_reloader(keyring_path, keyring)

    LOG.info(f'Watching keyring directory {keyring_path}...')
    reloader.start()

    LOG.info('Starting the daemon...')
    controller.start()

    try:
        loop.run_until_complete(_sleep())
    except KeyboardInterrupt:
        LOG.info("Finishing...")
    except:
        LOG.exception('Unexpected exception caught, your system may be unstable')
    finally:
        LOG.info('Shutting down keyring watcher and the daemon...')
        reloader.stop()
        reloader.join()
        controller.stop()

    LOG.info("Done")


if __name__ == '__main__':
    _main()
