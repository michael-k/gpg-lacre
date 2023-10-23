"""File-based keyring.

It's a wrapper over GnuPG module that just executes gpg command.
'"""

import logging
import GnuPG
import copy
from os import stat
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer
from asyncio import Semaphore, create_task, get_event_loop, run
import lacre.text as text
import lacre.config as conf
from lacre._keyringcommon import KeyRing, KeyCache

LOG = logging.getLogger(__name__)


def _sanitize(keys):
    sanitize = text.choose_sanitizer(conf.get_item('default', 'mail_case_insensitive'))
    return {fingerprint: sanitize(keys[fingerprint]) for fingerprint in keys}


class FileKeyRing(KeyRing):
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
        return create_task(self._load(), 'LoadTask')

    async def _load(self):
        last_mod = self._read_mod_time()
        LOG.debug(f'Keyring was last modified: {last_mod}')
        if self._is_modified(last_mod):
            LOG.debug('Keyring has been modified')
            async with self._sema:
                LOG.debug('About to re-load the keyring')
                self.replace_keyring(self._load_keyring_from(self._path))
        else:
            LOG.debug('Keyring not modified recently, continuing')

        self._last_mod = self._read_mod_time()

    reload = load

    def replace_keyring(self, keys: dict):
        """Overwrite previously stored key cache with KEYS."""
        keys = _sanitize(keys)

        LOG.info(f'Storing {len(keys)} keys')
        self._keys = keys

    def _read_mod_time(self) -> int:
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

    def __repr__(self) -> str:
        """Return text representation of this keyring."""
        return '<KeyRing path=%s last_mod=%d>' % (self._path, self._last_mod)

    def post_init_hook(self):
        self._reloader = init_reloader(self._path, self)
        LOG.info(f'Watching keyring directory {self._path}...')
        self._reloader.start()

    def shutdown(self):
        self._reloader.stop()
        self._reloader.join()


class KeyringModificationListener(FileSystemEventHandler):
    """A filesystem event listener that triggers key cache reload."""

    def __init__(self, keyring: FileKeyRing):
        """Initialise a listener with a callback to be executed upon each change."""
        self._keyring = keyring

    def handle(self, event: FileSystemEvent):
        """Reload keys upon FS event."""
        LOG.debug('FS event: %s, %s', event.event_type, event.src_path)
        if 'pubring.kbx' in event.src_path:
            LOG.info('Reloading %s on event: %s', self._keyring, event)
            self._keyring.reload()

    # All methods should do the same: reload the key cache.
    # on_created = handle
    # on_deleted = handle
    on_modified = handle


def init_reloader(keyring_dir: str, reloader) -> KeyringModificationListener:
    """Initialise a reloader for the keyring."""
    listener = KeyringModificationListener(reloader)
    observer = Observer()
    observer.schedule(listener, keyring_dir, recursive=False)
    return observer


def freeze_and_load_keys():
    """Load and return keys.

    Doesn't refresh the keys when they change on disk.
    '"""
    keyring_dir = conf.get_item('gpg', 'keyhome')
    keyring = FileKeyRing(keyring_dir)
    return run(keyring.freeze_identities())
