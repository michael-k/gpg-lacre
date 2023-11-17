"""Lacre identity and key repositories."""

from sqlalchemy import select, delete, and_
import logging

import lacre.dbschema as db

LOG = logging.getLogger(__name__)


class IdentityRepository:
    def __init__(self, identity_table, connection):
        self._identities = identity_table
        self._conn = connection

    def register(self, email, fingerprint):
        # TODO: upsert
        self._identities.insert().values(email=email, fingerprint=fingerprint)


class KeyConfirmationQueue:
    """Encapsulates access to gpgmw_keys table."""

    # Default number of items retrieved from the database.
    keys_read_max = 100

    def __init__(self, keys_table, connection):
        self._keys = keys_table
        self._conn = connection

    def fetch_keys(self, /, max_keys=None):
        """Runs a query to retrieve at most `keys_read_max` keys and returns db result."""
        max_keys = max_keys or self.keys_read_max

        selq = select(self._keys.c.publickey, self._keys.c.id, self._keys.c.email)\
            .where(and_(self._keys.c.status == db.ST_DEFAULT, self._keys.c.confirm == ""))\
            .limit(max_keys)

        LOG.debug('Retrieving keys to be processed: %s', selq)
        return self._conn.execute(selq)

    def fetch_keys_to_delete(self):
        seldel = select(self._keys.c.email, self._keys.c.id).where(self._keys.c.status == db.ST_TO_BE_DELETED).limit(self.keys_read_max)
        return self._conn.execute(seldel)

    def delete_keys(self, row_id, /, email=None):
        """Remove key from the database."""
        if email is not None:
            delq = delete(self._keys).where(and_(self._keys.c.email == email, self._keys.c.id != row_id))
        else:
            delq = delete(self._keys).where(self._keys.c.id != row_id)

        LOG.debug('Deleting public keys associated with confirmed email: %s', delq)
        self._conn.execute(delq)

    def mark_accepted(self, row_id):
        modq = self._keys.update().where(self._keys.c.id == row_id).values(status=db.ST_IMPORTED)
        LOG.debug("Key imported, updating key: %s", modq)

        self._conn.execute(modq)
