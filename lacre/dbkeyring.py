"""Database-backed keyring implementation."""

from lacre._keyringcommon import KeyRing, KeyCache
import logging
import sqlalchemy
from sqlalchemy.sql import select

LOG = logging.getLogger(__name__)


class KeyRingSchema:
    def __init__(self):
        self._meta = sqlalchemy.MetaData()
        self._id_table = self._identities()

    def _identities(self):
        lacre_id = sqlalchemy.Table('identities', self._meta,
            sqlalchemy.Column('email', sqlalchemy.String(256), index=True),
            sqlalchemy.Column('key_id', sqlalchemy.String(64), index=True))
        return lacre_id

    def identities(self):
        return self._id_table


class DatabaseKeyRing(KeyRing):
    """Database-backed key storage."""

    def __init__(self, database_url, schema: KeyRingSchema):
        self._schema = schema
        self._url = database_url
        self._initialised = False

    def _ensure_initialised(self):
        if not self._initialised:
            self._engine = sqlalchemy.create_engine(self._url)
            self._connection = self._engine.connect()

    def load(self):
        """Do nothing, database contents doesn't need to be cached."""
        pass

    async def freeze_identities(self) -> KeyCache:
        """Return a static, async-safe copy of the identity map."""
        self._ensure_initialised()
        return self._load_identities()

    def _load_identities(self) -> KeyCache:
        identities = self._schema.identities()
        all_identities = select(identities.c.key_id, identities.c.email)
        result = self._connection.execute(all_identities)
        LOG.debug('Retrieving all keys')
        return KeyCache({key_id: email for key_id, email in result})
