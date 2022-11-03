"""Mail operations for a given recipient.

There are 3 operations available:

- OpenPGPEncrypt: to deliver the message to a recipient with an OpenPGP public
  key available.

- SMimeEncrypt: to deliver the message to a recipient with an S/MIME
  certificate.

- KeepIntact: a no-operation (implementation of the Null Object pattern), used
  for messages already encrypted or those who haven't provided their keys or
  certificates.
"""

import logging
import lacre.core as core
from email.message import Message
from email.policy import SMTP


LOG = logging.getLogger(__name__)


class MailOperation:
    """Contract for an operation to be performed on a message."""

    def __init__(self, recipients=[]):
        """Initialise the operation with a recipient."""
        self._recipients = recipients

    def perform(self, message: Message) -> bytes:
        """Perform this operation on MESSAGE.

        Return target message.
        """
        raise NotImplementedError(self.__class__())

    def recipients(self):
        """Return list of recipients of the message."""
        return self._recipients

    def add_recipient(self, recipient):
        """Register another message recipient."""
        self._recipients.append(recipient)


class OpenPGPEncrypt(MailOperation):
    """OpenPGP-encrypt the message."""

    def __init__(self, recipients, keys, keyhome):
        """Initialise encryption operation."""
        super().__init__(recipients)
        self._keys = keys
        self._keyhome = keyhome

    def extend_keys(self, keys):
        """Register GPG keys to encrypt this message for."""
        self._keys.extend(keys)

    def __repr__(self):
        """Generate a representation with just method and key."""
        return f"<{type(self).__name__} {self._recipients} {self._keys}>"


class InlineOpenPGPEncrypt(OpenPGPEncrypt):
    """Inline encryption strategy."""

    def __init__(self, recipients, keys, keyhome):
        """Initialise strategy object."""
        super().__init__(recipients, keys, keyhome)

    def perform(self, msg: Message) -> bytes:
        """Encrypt with PGP Inline."""
        LOG.debug('Sending PGP/Inline...')
        return core._gpg_encrypt_to_bytes(msg,
                                          self._keys, self._recipients,
                                          core._encrypt_all_payloads_inline)


class MimeOpenPGPEncrypt(OpenPGPEncrypt):
    """MIME encryption strategy."""

    def __init__(self, recipients, keys, keyhome):
        """Initialise strategy object."""
        super().__init__(recipients, keys, keyhome)

    def perform(self, msg: Message) -> bytes:
        """Encrypt with PGP MIME."""
        LOG.debug('Sending PGP/MIME...')
        return core._gpg_encrypt_to_bytes(msg,
                                          self._keys, self._recipients,
                                          core._encrypt_all_payloads_mime)


class SMimeEncrypt(MailOperation):
    """S/MIME encryption operation."""

    def __init__(self, recipient, email, certificate):
        """Initialise S/MIME encryption for a given EMAIL and CERTIFICATE."""
        super().__init__(recipient)
        self._email = email
        self._cert = certificate

    def perform(self, message: Message) -> bytes:
        """Encrypt with a certificate."""
        LOG.warning(f"Delivering clear-text to {self._recipients}")
        return message.as_bytes(policy=SMTP)

    def __repr__(self):
        """Generate a representation with just method and key."""
        return f"<S/MIME {self._recipients}, {self._cert}>"


class KeepIntact(MailOperation):
    """A do-nothing operation (Null Object implementation).

    This operation should be used for mail that's already encrypted.
    """

    def __init__(self, recipients):
        """Initialise pass-through operation for a given recipient."""
        super().__init__(recipients)

    def perform(self, message: Message) -> bytes:
        """Return MESSAGE unmodified."""
        return message.as_bytes(policy=SMTP)

    def __repr__(self):
        """Return representation with just method and email."""
        return f"<KeepIntact {self._recipients}>"
