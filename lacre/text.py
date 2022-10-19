import sys
import re
import logging

import lacre.config as conf

# The standard way to encode line-ending in email:
EOL = "\r\n"

PGP_INLINE_BEGIN = b"-----BEGIN PGP MESSAGE-----"
PGP_INLINE_END = b"-----END PGP MESSAGE-----"


LOG = logging.getLogger(__name__)


def parse_content_type(content_type):
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


def sanitize_case_sense(address):
    """Sanitize email case."""
    # TODO: find a way to make it more unit-testable
    if conf.flag_enabled('default', 'mail_case_insensitive'):
        address = address.lower()
    else:
        splitted_address = address.split('@')
        if len(splitted_address) > 1:
            address = splitted_address[0] + '@' + splitted_address[1].lower()

    return address


def is_pgp_inline(payload) -> bool:
    """Find out if the payload (bytes) contains PGP/INLINE markers."""
    return PGP_INLINE_BEGIN in payload and PGP_INLINE_END in payload
