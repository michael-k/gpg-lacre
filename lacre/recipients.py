#
# gpg-mailgate
#
# This file is part of the gpg-mailgate source code.
#
# gpg-mailgate is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gpg-mailgate source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

"""Recipient processing package.

Defines:
- GpgRecipient, wrapper for user's email and identity.
- RecipientList, a wrapper for lists of GpgRecipient objects.
"""

import logging
import lacre.config as conf
import lacre.keyring as kcache
import lacre.text as text

LOG = logging.getLogger(__name__)


class GpgRecipient:
    """A tuple-like object that contains GPG recipient data."""

    def __init__(self, left, right):
        """Initialise a tuple-like object that contains GPG recipient data."""
        self._left = left
        self._right = right

    def __getitem__(self, index):
        """Pretend this object is a tuple by returning an indexed tuple element."""
        if index == 0:
            return self._left
        elif index == 1:
            return self._right
        else:
            raise IndexError()

    def __repr__(self):
        """Return textual representation of this GPG Recipient."""
        return f"GpgRecipient({self._left!r}, {self._right!r})"

    def email(self):
        """Return this recipient's email address."""
        return self._left

    def key(self):
        """Return this recipient's key ID."""
        return self._right


class RecipientList:
    """Encalsulates two lists of recipients.

    First list contains addresses, the second - GPG identities.
    """

    def __init__(self, recipients=[], keys=[]):
        """Initialise lists of recipients and identities."""
        self._recipients = [GpgRecipient(email, key) for (email, key) in zip(recipients, keys)]

    def emails(self):
        """Return list of recipients."""
        LOG.debug('Recipient emails from: %s', self._recipients)
        return [r.email() for r in self._recipients]

    def keys(self):
        """Return list of GPG identities."""
        LOG.debug('Recipient keys from: %s', self._recipients)
        return [r.key() for r in self._recipients]

    def __iadd__(self, recipient: GpgRecipient):
        """Append a recipient."""
        LOG.debug('Adding %s to %s', recipient, self._recipients)
        self._recipients.append(recipient)
        LOG.debug('Added; got: %s', self._recipients)
        return self

    def __len__(self):
        """Provide len().

        With this method, it is possible to write code like:

        rl = RecipientList()
        if rl:
            # do something
        """
        return len(self._recipients)


def identify_gpg_recipients(recipients, keys: kcache.KeyCache):
    """Split recipient list into GPG and non-GPG ones."""
    # This list will be filled with pairs (M, N), where M is the destination
    # address we're going to deliver the message to and N is the identity we're
    # going to encrypt it for.
    gpg_recipients = list()

    # This will be the list of recipients that haven't provided us with their
    # public keys.
    cleartext_recipients = list()

    # In "strict mode", only keys included in configuration are used to encrypt
    # email.
    strict_mode = conf.strict_mode()

    for recipient in recipients:
        gpg_recipient = _find_key(recipient, keys, strict_mode)
        if gpg_recipient is not None:
            gpg_recipients.append(gpg_recipient)
        else:
            cleartext_recipients.append(recipient)

    LOG.debug('Collected recipients; GPG: %s; cleartext: %s', gpg_recipients, cleartext_recipients)
    return gpg_recipients, cleartext_recipients


def _find_key(recipient, keys, strict_mode):
    own_key = _try_configured_key(recipient, keys)
    if own_key is not None:
        return GpgRecipient(own_key[0], own_key[1])

    direct_key = _try_direct_key_lookup(recipient, keys, strict_mode)
    if direct_key is not None:
        return GpgRecipient(direct_key[0], direct_key[1])

    domain_key = _try_configured_domain_key(recipient, keys)
    if domain_key is not None:
        return GpgRecipient(domain_key[0], domain_key[1])

    return None


def _try_configured_key(recipient, keys):
    if conf.config_item_set('enc_keymap', recipient):
        key = conf.get_item('enc_keymap', recipient)
        if key in keys:
            LOG.debug(f"Found key {key} configured for {recipient}")
            return (recipient, key)

    LOG.debug(f"No configured key found for {recipient}")
    return None


def _try_direct_key_lookup(recipient, keys, strict_mode):
    if strict_mode:
        return None

    if keys.has_email(recipient):
        LOG.info(f"Found key for {recipient}")
        return recipient, recipient

    (newto, topic) = text.parse_delimiter(recipient)
    if keys.has_email(newto):
        LOG.info(f"Found key for {newto}, stripped {recipient}")
        return recipient, newto

    return None


def _try_configured_domain_key(recipient, keys):
    parts = recipient.split('@')
    if len(parts) != 2:
        return None

    domain = parts[1]
    if conf.config_item_set('enc_domain_keymap', domain):
        domain_key = conf.get_item('enc_domain_keymap', domain)
        if domain_key in keys:
            LOG.debug(f"Found domain key {domain_key} for {recipient}")
            return recipient, domain_key

    LOG.debug(f"No domain key for {recipient}")
    return None
