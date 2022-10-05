"""A cache of OpenPGP keys known to Lacre."""

import lacre.text as text
import logging

import GnuPG

LOG = logging.getLogger(__name__)


class KeyCache:
    """A store for OpenPGP keys.

    Key case is sanitised while loading from GnuPG if so
    configured.  See mail_case_insensitive parameter in section
    [default].
    """

    def __init__(self, keyring_dir: str = None):
        """Initialise an empty cache.

        With keyring_dir given, set location of the directory from which keys should be loaded.
        """
        self._keys = dict()
        self._keyring_dir = keyring_dir

    def __getitem__(self, fingerpring):
        """Look up email assigned to the given fingerprint."""
        return self._keys[fingerpring]

    def __setitem__(self, fingerprint, email):
        """Assign an email to a fingerpring, overwriting it if it was already present."""
        self._keys[fingerprint] = email

    def __contains__(self, fingerprint):
        """Check if the given fingerprint is assigned to an email."""
        # This method has to be present for KeyCache to be a dict substitute.
        # See mailgate, function _identify_gpg_recipients.
        return fingerprint in self._keys

    def has_email(self, email):
        """Check if cache contains a key assigned to the given email."""
        return email in self._keys.values()

    def load(self):
        """Load keyring, replacing any previous contents of the cache."""
        self.replace_keyring(self._load_keyring_from(self._keyring_dir))

    reload = load

    def load_keyring(self, keyhome: str):
        """Add all identities from keyring stored in KEYHOME."""
        self.extend_keyring(self._load_keyring_from(keyhome))

    def _load_keyring_from(self, keyring_dir):
        return GnuPG.public_keys(keyring_dir)

    def replace_keyring(self, keys: dict):
        """Overwrite previously stored key cache with KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        LOG.info(f'Loaded {len(keys)} keys')
        self._keys = keys

    def extend_keyring(self, keys: dict):
        """Add all keys from KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        LOG.info(f'Loaded {len(keys)} keys')
        self._keys.update(keys)
