"""A cache of OpenPGP keys known to Lacre."""

import lacre.text as text

import GnuPG


class KeyCache:
    """A store for OpenPGP keys.

    Key case is sanitised while loading from GnuPG if so
    configured.  See mail_case_insensitive parameter in section
    [default].
    """

    def __init__(self):
        """Initialise an empty cache."""
        self._keys = dict()

    def __getitem__(self, email):
        return self._keys[email]

    def __setitem__(self, email, fingerprint):
        self._keys[email] = fingerprint

    def __contains__(self, fingerprint):
        """Check if the given fingerprint is assigned to an email."""
        # This method has to be present for KeyCache to be a dict substitute.
        # See mailgate, function _identify_gpg_recipients.
        return fingerprint in self._keys

    def has_email(self, email):
        return email in self._keys.values()

    def load_keyring(self, keyhome: str):
        """Add all identities from keyring stored in KEYHOME."""
        self.extend_keyring(GnuPG.public_keys(keyhome))

    def replace_keyring(self, keys: dict):
        """Overwrite previously stored key cache with KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        self._keys = keys

    def extend_keyring(self, keys: dict):
        """Add all keys from KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        self._keys.update(keys)
