"""Lacre identity and key repositories."""

from sqlalchemy import create_engine, select, delete, and_, func
from sqlalchemy.exc import OperationalError
import logging

from lacre.config import flag_enabled, config_item_set, get_item, PoolingMode
from lacre._keyringcommon import KeyRing, KeyCache
import lacre.dbschema as db

LOG = logging.getLogger(__name__)


_HOUR_IN_SECONDS = 3600

# Internal state
_engine = None


def init_engine(url, db_debug=False):
    global _engine

    if not _engine:
        config = _conn_config(db_debug)
        _engine = create_engine(url, **config)

    return _engine


def _conn_config(db_debug):
    config = dict()

    mode = PoolingMode.from_config('database', 'pooling_mode', required=True)
    if mode is PoolingMode.OPTIMISTIC:
        # Optimistic distonnect-handling: recycle connections.
        config['pool_recycle'] = int(get_item('database', 'max_connection_age', _HOUR_IN_SECONDS))
    elif mode is PoolingMode.PESSIMISTIC:
        # Pessimistic disconnect-handling: pre_ping.
        config['pool_pre_ping'] = True

    # Additional pool settings
    if config_item_set('database', 'pool_size'):
        config['pool_size'] = int(get_item('database', 'pool_size'))

    if config_item_set('database', 'max_overflow'):
        config['max_overflow'] = int(get_item('database', 'max_overflow'))

    if db_debug:
        config['echo'] = 'debug'
        config['echo_pool'] = 'debug'

    LOG.debug('Database engine configuration: %s', config)
    return config


class IdentityRepository(KeyRing):
    def __init__(self, /, connection=None, *, engine):
        self._identities = db.LACRE_IDENTITIES
        self._engine = engine

    def register_or_update(self, email, fprint):
        assert email, "email is mandatory"
        assert fprint, "fprint is mandatory"

        if self._exists(email):
            self._update(email, fprint)
        else:
            self._insert(email, fprint)

    def _exists(self, email: str) -> bool:
        selq = select(self._identities.c.email).where(self._identities.c.email == email)
        with self._engine.connect() as conn:
            return [e for e in conn.execute(selq)]

    def _insert(self, email, fprint):
        insq = self._identities.insert().values(email=email, fingerprint=fprint)

        LOG.debug('Registering identity: %s -- %s', insq, insq.compile().params)
        with self._engine.connect() as conn:
            conn.execute(insq)

    def _update(self, email, fprint):
        upq = self._identities.update() \
            .values(fingerprint=fprint) \
            .where(self._identities.c.email == email)

        LOG.debug('Updating identity: %s -- %s', upq, upq.compile().params)
        with self._engine.connect() as conn:
            conn.execute(upq)

    def delete(self, email):
        delq = delete(self._identities).where(self._identities.c.email == email)
        LOG.debug('Deleting assigned keys: %s -- %s', delq, delq.compile().params)

        with self._engine.connect() as conn:
            conn.execute(delq)

    def delete_all(self):
        LOG.warn('Deleting all identities from the database')

        delq = delete(self._identities)
        with self._engine.connect() as conn:
            conn.execute(delq)

    def freeze_identities(self) -> KeyCache:
        """Return a static, async-safe copy of the identity map.

        Depending on the value of [daemon]bounce_on_keys_missing value,
        if we get a database exception, this method will either return
        empty collection or let the exception be propagated.
        """
        try:
            return self._load_identities()
        except OperationalError:
            if flag_enabled('daemon', 'bounce_on_keys_missing'):
                raise
            else:
                LOG.exception('Failed to load keys, returning empty collection')
                return KeyCache({})

    def _load_identities(self) -> KeyCache:
        all_identities = select(self._identities.c.fingerprint, self._identities.c.email)
        with self._engine.connect() as conn:
            result = conn.execute(all_identities)
            LOG.debug('Retrieving all keys: %s', all_identities)
            return KeyCache({key_id: email for key_id, email in result})


class KeyConfirmationQueue:
    """Encapsulates access to lacre_keys table."""

    # Default number of items retrieved from the database.
    keys_read_max = 100

    def __init__(self, /, engine):
        self._keys = db.LACRE_KEYS
        self._engine = engine

    def fetch_keys(self, /, max_keys=None):
        """Runs a query to retrieve at most `keys_read_max` keys and returns db result."""
        max_keys = max_keys or self.keys_read_max
        LOG.debug('Row limit: %d', max_keys)

        selq = select(self._keys.c.publickey, self._keys.c.id, self._keys.c.email) \
            .where(and_(self._keys.c.status == db.ST_DEFAULT, self._keys.c.confirm == db.CO_CONFIRMED)) \
            .limit(max_keys)

        LOG.debug('Retrieving keys to be processed: %s -- %s', selq, selq.compile().params)
        with self._engine.connect() as conn:
            return [e for e in conn.execute(selq)]

    def count_keys(self):
        selq = select(func.count(self._keys.c.id)) \
            .where(and_(self._keys.c.status == db.ST_DEFAULT, self._keys.c.confirm == db.CO_CONFIRMED))

        LOG.debug('Counting all keys: %s -- %s', selq, selq.compile().params)
        try:
            with self._engine.connect() as conn:
                res = conn.execute(selq)
                # This is a 1-element tuple.
                return res.one_or_none()[0]
        except OperationalError:
            LOG.exception('Cannot count keys')
            return None

    def fetch_keys_to_delete(self):
        seldel = select(self._keys.c.email, self._keys.c.id) \
            .where(self._keys.c.status == db.ST_TO_BE_DELETED) \
            .limit(self.keys_read_max)

        with self._engine.connect() as conn:
            return [e for e in conn.execute(seldel)]

    def delete_keys(self, row_id, /, email=None):
        """Remove key from the database."""
        if email is not None:
            LOG.debug('Deleting key: id=%s, email=%s', row_id, email)
            delq = delete(self._keys).where(and_(self._keys.c.email == email, self._keys.c.id == row_id))
        else:
            LOG.debug('Deleting key: id=%s', row_id)
            delq = delete(self._keys).where(self._keys.c.id == row_id)

        with self._engine.connect() as conn:
            LOG.debug('Deleting public keys associated with confirmed email: %s', delq)
            conn.execute(delq)

    def delete_key_by_email(self, email):
        """Remove keys linked to the given email from the database."""
        delq = delete(self._keys).where(self._keys.c.email == email)

        LOG.debug('Deleting email for: %s', email)
        with self._engine.connect() as conn:
            conn.execute(delq)

    def mark_accepted(self, row_id):
        modq = self._keys.update().where(self._keys.c.id == row_id).values(status=db.ST_IMPORTED)
        LOG.debug("Key imported, updating key: %s", modq)

        with self._engine.connect() as conn:
            conn.execute(modq)
