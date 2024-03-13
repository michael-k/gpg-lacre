"""SMTP transport module."""

import smtplib
import logging
from typing import AnyStr, List

import lacre.config as conf
from lacre.mailop import MailSerialisationException

# Mail status constants.
#
# These are the only values that our mail handler is allowed to return.
RESULT_OK = '250 OK'
RESULT_TRANS_FAIL = '451 Aborted: error in processing'
RESULT_PERM_FAIL = '554 Transaction failed'

# See RFC 5321, section 4.2.1 "Reply Code Severities and Theory" for more
# information on SMTP reply codes.
RESP_TRANSIENT_NEG = 4
RESP_PERMANENT_NEG = 5

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
        smtp = smtplib.SMTP(relay.name, relay.port)
        if conf.flag_enabled('relay', 'starttls'):
            smtp.starttls()
        smtp.sendmail(from_addr, recipients, message)
    else:
        LOG.info("No recipient found")


class TransientFailure(BaseException):
    """Signals a transient delivery failure (4xx SMTP reply).

    Message should be bounced and re-sent later.
    """
    pass


class PermanentFailure(BaseException):
    """Signals a permanent delivery failure (5xx SMTP reply)."""
    pass


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
        smtp = smtplib.SMTP(relay.name, relay.port)

        if conf.flag_enabled('relay', 'starttls'):
            smtp.starttls()

        try:
            smtp.sendmail(self._from_addr, recipients, message)
        except smtplib.SMTPResponseException as re:
            resp_class = self._get_class(re.smtp_code)

            if resp_class == RESP_TRANSIENT_NEG:
                LOG.warning('Transient delivery failure: %s', re)
                raise TransientFailure()
            elif resp_class == RESP_PERMANENT_NEG:
                LOG.error('Permanent delivery failure: %s', re)
                raise PermanentFailure()
        except smtplib.SMTPException as err:
            LOG.error('Failed to deliver message: %s', err)
            raise PermanentFailure()
        except UnicodeEncodeError as uee:
            LOG.error('Failed to deliver for non-SMTP reason', uee)
            raise MailSerialisationException(uee)

    def _get_class(self, resp_code):
        return int(resp_code / 100)
