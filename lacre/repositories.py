"""Lacre identity and key repositories."""

from sqlalchemy import create_engine, select, delete, and_, func
from sqlalchemy.exc import OperationalError
import logging

from lacre._keyringcommon import KeyRing, KeyCache
import lacre.dbschema as db

LOG = logging.getLogger(__name__)


# Internal state
_engine = None


def connect(url):
    global _engine

    if not _engine:
        _engine = create_engine(url)

    return _engine.connect()

class IdentityRepository(KeyRing):
    def __init__(self, /, connection=None, db_url=None):
        self._identities = db.LACRE_IDENTITIES
        self._conn = connection
        self._url = db_url
        self._initialised = connection is not None

    def register_or_update(self, email, fprint):
        assert email, "email is mandatory"
        assert fprint, "fprint is mandatory"

        if self._exists(email):
            self._update(email, fprint)
        else:
            self._insert(email, fprint)

    def _exists(self, email: str) -> bool:
        self._ensure_connected()
        selq = select(self._identities.c.email).where(self._identities.c.email == email)
        return [e for e in self._conn.execute(selq)]

    def _insert(self, email, fprint):
        self._ensure_connected()
        insq = self._identities.insert().values(email=email, fingerprint=fprint)

        LOG.debug('Registering identity %s: %s', email, insq)
        self._conn.execute(insq)

    def _update(self, email, fprint):
        self._ensure_connected()
        upq = self._identities.update() \
            .values(fingerprint=fprint) \
            .where(self._identities.c.email == email)

        LOG.debug('Updating identity %s: %s', email, upq)
        self._conn.execute(upq)

    def _ensure_connected(self):
        if not self._initialised:
            LOG.debug('Connecting with %s', self._url)
            self._conn = connect(self._url)

    def delete(self, email):
        self._ensure_connected()

        delq = delete(self._identities).where(self._identities.c.email == email)
        LOG.debug('Deleting keys assigned to %s', email)

        self._conn.execute(delq)

    def delete_all(self):
        LOG.warn('Deleting all identities from the database')

        delq = delete(self._identities)
        self._conn.execute(delq)

    def freeze_identities(self) -> KeyCache:
        """Return a static, async-safe copy of the identity map.

        Depending on the value of [daemon]bounce_on_keys_missing value,
        if we get a database exception, this method will either return
        empty collection or let the exception be propagated.
        """
        self._ensure_connected()
        try:
            return self._load_identities()
        except OperationalError:
            if conf.flag_enabled('daemon', 'bounce_on_keys_missing'):
                raise
            else:
                LOG.exception('Failed to load keys, returning empty collection')
                return KeyCache({})

    def _load_identities(self) -> KeyCache:
        all_identities = select(self._identities.c.fingerprint, self._identities.c.email)
        result = self._conn.execute(all_identities)
        LOG.debug('Retrieving all keys')
        return KeyCache({key_id: email for key_id, email in result})


class KeyConfirmationQueue:
    """Encapsulates access to lacre_keys table."""

    # Default number of items retrieved from the database.
    keys_read_max = 100

    def __init__(self, connection):
        self._keys = db.LACRE_KEYS
        self._conn = connection

    def fetch_keys(self, /, max_keys=None):
        """Runs a query to retrieve at most `keys_read_max` keys and returns db result."""
        max_keys = max_keys or self.keys_read_max

        selq = select(self._keys.c.publickey, self._keys.c.id, self._keys.c.email) \
            .where(and_(self._keys.c.status == db.ST_DEFAULT, self._keys.c.confirm == "")) \
            .limit(max_keys)

        LOG.debug('Retrieving keys to be processed: %s', selq)
        return self._conn.execute(selq)

    def count_keys(self):
        selq = select(func.count(self._keys.c.id))

        LOG.debug('Counting all keys: %s', selq)
        try:
            c = [cnt for cnt in self._conn.execute(selq)]

            # Result is an iterable of tuples:
            return c[0][0]
        except OperationalError:
            LOG.exception('Cannot count keys')
            return None

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
