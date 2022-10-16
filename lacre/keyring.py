"""Data structures and utilities to make keyring access easier.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

import lacre.text as text
import logging
from os import stat
from watchdog.events import FileSystemEventHandler

import GnuPG

LOG = logging.getLogger(__name__)


class KeyCacheMisconfiguration(Exception):
    """Exception used to signal that KeyCache is misconfigured."""


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
        self._last_mod = None

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
        LOG.debug('Reloading keys...')

        if self._keyring_dir is None:
            LOG.error('Keyringn directory not set!')
            raise KeyCacheMisconfiguration("Keyring directory not configured")

        last_mod = self._read_mod_time()
        if self._is_modified(last_mod):
            self.replace_keyring(self._load_keyring_from(self._keyring_dir))

        self._last_mod = self._read_mod_time()

    reload = load

    def load_keyring_from(self, keyhome: str):
        """Add all identities from keyring stored in KEYHOME."""
        self.extend_keyring(self._load_keyring_from(keyhome))

    def _load_keyring_from(self, keyring_dir):
        return GnuPG.public_keys(keyring_dir)

    def replace_keyring(self, keys: dict):
        """Overwrite previously stored key cache with KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        LOG.info(f'Storing {len(keys)} keys')
        self._keys = keys

    def extend_keyring(self, keys: dict):
        """Add all keys from KEYS."""
        for fingerprint in keys:
            keys[fingerprint] = text.sanitize_case_sense(keys[fingerprint])

        LOG.info(f'Adding {len(keys)} keys')
        self._keys.update(keys)

    def _is_modified(self, last_mod):
        if self._last_mod is None:
            LOG.debug('Keyring not loaded before')
            return True
        elif self._last_mod != last_mod:
            LOG.debug('Keyring directory mtime changed')
            return True
        else:
            LOG.debug('Keyring not modified ')
            return False

    def _read_mod_time(self):
        # (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime)
        MTIME = 8
        st = stat(self._keyring_dir)
        return st[MTIME]


class KeyringModificationListener(FileSystemEventHandler):
    """A filesystem event listener that triggers key cache reload."""

    def __init__(self, cache: KeyCache):
        """Initialise a listener with a callback to be executed upon each change."""
        self._cache = cache

    def handle(self, event):
        """Reload keys upon FS event."""
        LOG.debug(f'Reloading on event {event!r}')
        self._cache.reload()

    # All methods should do the same: reload the key cache.
    # on_created = handle
    # on_deleted = handle
    on_modified = handle
