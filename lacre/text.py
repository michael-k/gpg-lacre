"""Basic payload-processing routines."""

import sys
import re
import logging
from email.message import Message


# The standard way to encode line-ending in email:
EOL = "\r\n"

PGP_INLINE_BEGIN = b"-----BEGIN PGP MESSAGE-----"
PGP_INLINE_END = b"-----END PGP MESSAGE-----"


LOG = logging.getLogger(__name__)


def parse_content_type(content_type: str):
    """Analyse Content-Type email header.

    Return a pair: type and sub-type.
    """
    parts = [p.strip() for p in content_type.split(';')]
    if len(parts) == 1:
        # No additional attributes provided.  Use default encoding.
        return (content_type, sys.getdefaultencoding())

    # At least one attribute provided.  Find out if any of them is named
    # 'charset' and if so, use it.
    ctype = parts[0]
    encoding = [p for p in parts[1:] if p.startswith('charset=')]
    if encoding:
        eq_idx = encoding[0].index('=')
        return (ctype, encoding[0][eq_idx+1:])
    else:
        return (ctype, sys.getdefaultencoding())


def parse_delimiter(address: str):
    """Parse an email with delimiter and topic.

    Return destination emaili and topic as a tuple.
    """
    withdelim = re.match('^([^\\+]+)\\+([^@]+)@(.*)$', address)
    LOG.debug(f'Parsed email: {withdelim!r}')

    if withdelim:
        return (withdelim.group(1) + '@' + withdelim.group(3), withdelim.group(2))
    else:
        return (address, None)


def _lowercase_whole_address(address: str):
    return address.lower()


def _lowercase_domain_only(address: str):
    parts = address.split('@', maxsplit=2)
    if len(parts) > 1:
        return parts[0] + '@' + parts[1].lower()
    else:
        return address


def choose_sanitizer(mail_case_insensitive: bool):
    """Return a function to sanitize email case sense."""
    if mail_case_insensitive:
        return _lowercase_whole_address
    else:
        return _lowercase_domain_only


def is_payload_pgp_inline(payload: bytes) -> bool:
    """Find out if the payload (bytes) contains PGP/inline markers."""
    return PGP_INLINE_BEGIN in payload and PGP_INLINE_END in payload


def is_message_pgp_inline(message: Message) -> bool:
    """Find out if a message is already PGP-Inline encrypted."""
    if message.is_multipart() or isinstance(message.get_payload(), list):
        # more than one payload, check each one of them
        return any(is_message_pgp_inline(m.payload()) for m in message.iter_parts())
    else:
        # one payload, check it
        return is_payload_pgp_inline(message.get_payload(decode=True))
