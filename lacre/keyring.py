"""Data structures and utilities to make keyring access easier.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

import lacre.config as conf
from lacre._keyringcommon import KeyRing, KeyCache
from lacre.dbschema import GPGMW_IDENTITIES
from lacre.repositories import IdentityRepository
import logging

LOG = logging.getLogger(__name__)


def init_keyring() -> KeyRing:
    """Initialise appropriate type of keyring."""
    url = conf.get_item('database', 'url')
    return IdentityRepository(db_url=url)


def freeze_and_load_keys() -> KeyCache:
    """Load and return keys.

    Doesn't refresh the keys when they change on disk.
    """
    keyring = init_keyring()
    return keyring.freeze_identities()
