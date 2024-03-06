"""SMTP transport module."""

import smtplib
import logging
from typing import AnyStr, List

import lacre.config as conf

# Mail status constants.
#
# These are the only values that our mail handler is allowed to return.
RESULT_OK = '250 OK'                              # delivered
RESULT_ABORT = '451 Aborted: error in processing' # aborted, retry later
RESULT_FAILED = '554 Transaction failed'          # failed

LOG = logging.getLogger(__name__)

# This is a left-over from old architecture.
from_addr = None


def register_sender(fromaddr):
    """Set module state: message sender address."""
    global from_addr
    LOG.warning('Setting global recipient: %s', fromaddr)
    from_addr = fromaddr


def send_msg(message: AnyStr, recipients: List[str]):
    """Send MESSAGE to RECIPIENTS to the mail relay."""
    global from_addr
    LOG.debug('Delivery from %s to %s', from_addr, recipients)

    recipients = [_f for _f in recipients if _f]
    if recipients:
        LOG.info(f"Sending email to: {recipients!r}")
        relay = conf.relay_params()
        smtp = smtplib.SMTP(relay[0], relay[1])
        if conf.flag_enabled('relay', 'starttls'):
            smtp.starttls()
        smtp.sendmail(from_addr, recipients, message)
    else:
        LOG.info("No recipient found")


class SendFrom:
    """A class wrapping the transport process."""

    def __init__(self, from_addr):
        """Initialise the transport."""
        self._from_addr = from_addr

    def __call__(self, message: AnyStr, recipients: List[str]):
        """Send the given message to all recipients from the list.

        - Message is the email object serialised to str or bytes.
        - Empty recipients are filtered out before communication.
        """
        recipients = [_f for _f in recipients if _f]

        if not recipients:
            LOG.warning("No recipient found")
            return

        LOG.info("Sending email to: %s", recipients)
        relay = conf.relay_params()
        smtp = smtplib.SMTP(relay[0], relay[1])

        if conf.flag_enabled('relay', 'starttls'):
            smtp.starttls()

        try:
            smtp.sendmail(self._from_addr, recipients, message)
        except smtplib.SMTPException:
            LOG.exception('Failed to deliver message')
