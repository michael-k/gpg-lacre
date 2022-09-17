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
import GnuPG


LOG = logging.getLogger(__name__)


class MailOperation:
    """Contract for an operation to be performed on a message."""

    def __init__(self, recipients=[]):
        """Initialise the operation with a recipient."""
        self._recipients = recipients

    def perform(self, message):
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

    def __init__(self, recipient, key, keyhome):
        """Initialise encryption operation."""
        super().__init__(recipient)
        self._key = key
        self._keyhome = keyhome

    def perform(self, message):
        """Encrypt MESSAGE with the given key."""
        enc = GnuPG.GPGEncryptor(self._keyhome)
        enc.update(message)
        encrypted, err = enc.encrypt()
        if err:
            LOG.error(f"Unable to encrypt message, delivering cleartext (gpg exit code: {err})")
            return message
        else:
            return encrypted

    def __repr__(self):
        """Generate a representation with just method and key."""
        return f"<OpenPGP {self._recipients} {self._key}>"


class SMimeEncrypt(MailOperation):
    """S/MIME encryption operation."""

    def __init__(self, recipient, email, certificate):
        """Initialise S/MIME encryption for a given EMAIL and CERTIFICATE."""
        super().__init__(recipient)
        self._email = email
        self._cert = certificate

    def perform(self, message):
        """Encrypt with a certificate."""
        LOG.warning(f"Delivering clear-text to {self._recipients}")
        return message

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

    def perform(self, message):
        """Return MESSAGE unmodified."""
        return message

    def __repr__(self):
        """Return representation with just method and email."""
        return f"<KeepIntact {self._recipients}>"
