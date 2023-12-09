"""Lacre Daemon, the Advanced Mail Filter message dispatcher."""

import logging
import lacre
from lacre.text import DOUBLE_EOL_BYTES
from lacre.stats import time_logger
import lacre.config as conf
import sys
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope
import asyncio
import email
from email.policy import SMTPUTF8

# Load configuration and init logging, in this order.  Only then can we load
# the last Lacre module, i.e. lacre.mailgate.
conf.load_config()
lacre.init_logging(conf.get_item("logging", "config"))
LOG = logging.getLogger('lacre.daemon')

from GnuPG import EncryptionException
import lacre.core as gate
import lacre.keyring as kcache
import lacre.transport as xport
from lacre.mailop import KeepIntact


class MailEncryptionProxy:
    """A mail handler dispatching to appropriate mail operation."""

    def __init__(self, keyring: kcache.KeyRing):
        """Initialise the mail proxy with a reference to the key cache."""
        self._keyring = keyring

    async def handle_DATA(self, server, session, envelope: Envelope):
        """Accept a message and either encrypt it or forward as-is."""
        with time_logger('Message delivery', LOG):
            try:
                keys = self._keyring.freeze_identities()
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

                send = xport.SendFrom(envelope.mail_from)
                for operation in gate.delivery_plan(envelope.rcpt_tos, message, keys):
                    LOG.debug(f"Sending mail via {operation!r}")
                    try:
                        new_message = operation.perform(message)
                        send(new_message, operation.recipients())
                    except EncryptionException as e:
                        # If the message can't be encrypted, deliver cleartext.
                        LOG.error('Unable to encrypt message, delivering in cleartext: %s', e)
                        if not isinstance(operation, KeepIntact):
                            self._send_unencrypted(operation, message, envelope, send)
                        else:
                            LOG.error(f'Cannot perform {operation}')

            except:
                LOG.exception('Unexpected exception caught, bouncing message')
                return xport.RESULT_ERROR

        return xport.RESULT_OK

    def _send_unencrypted(self, operation, message, envelope, send: xport.SendFrom):
        keep = KeepIntact(operation.recipients())
        new_message = keep.perform(message)
        send(new_message, operation.recipients())

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

    def _seconds_between(self, start_ms, end_ms) -> float:
        return (end_ms - start_ms) * 1000


def _init_controller(keys: kcache.KeyRing, max_body_bytes=None, tout: float = 5):
    proxy = MailEncryptionProxy(keys)
    host, port = conf.daemon_params()
    LOG.info(f"Initialising a mail Controller at {host}:{port}")
    return Controller(proxy, hostname=host, port=port,
                      ready_timeout=tout,
                      data_size_limit=max_body_bytes)


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


async def _main():
    _validate_config()

    keyring_path = conf.get_item('gpg', 'keyhome')
    max_data_bytes = int(conf.get_item('daemon', 'max_data_bytes', 2**25))

    loop = asyncio.get_event_loop()

    try:
        keyring = kcache.init_keyring()
        controller = _init_controller(keyring, max_data_bytes)

        keyring.post_init_hook()

        LOG.info('Starting the daemon...')
        controller.start()

        await _sleep()
    except KeyboardInterrupt:
        LOG.info("Finishing...")
    except:
        LOG.exception('Unexpected exception caught, your system may be unstable')
    finally:
        LOG.info('Shutting down keyring watcher and the daemon...')
        keyring.shutdown()
        controller.stop()

    LOG.info("Done")


if __name__ == '__main__':
    asyncio.run(_main())
