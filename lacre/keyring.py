"""Data structures and utilities to make keyring access easier.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

import lacre.config as conf
from lacre._keyringcommon import KeyRing, KeyCache
import lacre.filekeyring as fk
import lacre.dbkeyring as dbk
import logging

LOG = logging.getLogger(__name__)


def init_keyring(mode, **kwargs) -> KeyRing:
    """Initialise appropriate type of keyring."""
    if mode == 'file' and 'loop' in kwargs:
        path = conf.get_item('gpg', 'keyhome')
        LOG.info('Initialising pubring.kbx-based keyring from %s with cache', path)
        return fk.FileKeyRing(path, kwargs['loop'])
    elif mode == 'database':
        url = conf.get_item('keyring', 'url')
        schema = dbk.KeyRingSchema()
        LOG.info('Initialising database keyring from %s', url)
        return dbk.DatabaseKeyRing(url, schema)
    else:
        LOG.error('Unsupported type of keyring: %s', mode)
