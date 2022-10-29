"""Data structures and utilities to make keyring access easier.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

import lacre.text as text
import lacre.config as conf
import logging
from os import stat
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from asyncio import Semaphore, create_task, get_event_loop
import copy

import GnuPG

LOG = logging.getLogger(__name__)


def _sanitize(keys):
    sanitize = text.choose_sanitizer(conf.get_item('default', 'mail_case_insensitive'))
    return {fingerprint: sanitize(keys[fingerprint]) for fingerprint in keys}


class KeyCacheMisconfiguration(Exception):
    """Exception used to signal that KeyCache is misconfigured."""


class KeyCache:
    """A store for OpenPGP keys.

    Key case is sanitised while loading from GnuPG if so
    configured.  See mail_case_insensitive parameter in section
    [default].
    """

    def __init__(self, keys: dict = None):
        """Initialise an empty cache.

        With keyring_dir given, set location of the directory from which keys should be loaded.
        """
        self._keys = keys

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

    def __repr__(self):
        """Return text representation of this object."""
        details = ' '.join(self._keys.keys())
        return f'<KeyCache {details}>'


class KeyRing:
    """A high-level adapter for GnuPG-maintained keyring directory.

    Its role is to keep a cache of keys present in the keyring,
    reload it when necessary and produce static copies of
    fingerprint=>email maps.
    """

    def __init__(self, path: str, loop=None):
        """Initialise the adapter."""
        self._path = path
        self._keys = self._load_and_sanitize()
        self._sema = Semaphore()
        self._last_mod = None
        self._loop = loop or get_event_loop()

    def _load_and_sanitize(self):
        keys = self._load_keyring_from(self._path)
        return _sanitize(keys)

    def _load_keyring_from(self, keyring_dir):
        return GnuPG.public_keys(keyring_dir)

    async def freeze_identities(self) -> KeyCache:
        """Return a static, async-safe copy of the identity map."""
        async with self._sema:
            keys = copy.deepcopy(self._keys)
            return KeyCache(keys)

    def load(self):
        """Load keyring, replacing any previous contents of the cache."""
        LOG.debug('Reloading keys...')
        tsk = create_task(self._load(), 'LoadTask')
        self._loop.run_until_complete(tsk)

    async def _load(self):
        last_mod = self._read_mod_time()
        if self._is_modified(last_mod):
            async with self._sema:
                self.replace_keyring(self._load_keyring_from(self._path))

        self._last_mod = self._read_mod_time()

    reload = load

    def replace_keyring(self, keys: dict):
        """Overwrite previously stored key cache with KEYS."""
        keys = _sanitize(keys)

        LOG.info(f'Storing {len(keys)} keys')
        self._keys = keys

    def _read_mod_time(self):
        # (mode, ino, dev, nlink, uid, gid, size, atime, mtime, ctime)
        #  0     1    2    3      4    5    6     7      8      9
        MTIME = 8
        st = stat(self._path)
        return st[MTIME]

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


class KeyringModificationListener(FileSystemEventHandler):
    """A filesystem event listener that triggers key cache reload."""

    def __init__(self, keyring: KeyRing):
        """Initialise a listener with a callback to be executed upon each change."""
        self._keyring = keyring

    def handle(self, event: FileSystemEvent):
        """Reload keys upon FS event."""
        if 'pubring.kbx' in event.src_path:
            LOG.debug(f'Reloading on event {event!r}')
            self._keyring.reload()

    # All methods should do the same: reload the key cache.
    # on_created = handle
    # on_deleted = handle
    on_modified = handle
