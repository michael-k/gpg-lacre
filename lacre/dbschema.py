"""Database schema for Lacre.

This definition includes:

- 'lacre_keys' -- temporary key storage, used by the frontend to submit keys and
  by webgate-cron script to import submitted keys.

- 'lacre_identities' -- identity catalogue, used by encryption logic to match
  emails with corresponding keys.

- 'lacre_locks' -- used only by the frontend.
"""

import sqlalchemy

# Values for lacre_keys.status column:
# - ST_DEFAULT: initial state;
# - ST_IMPORTED: key has been successfully processed by cron job;
# - ST_TO_BE_DELETED: key can be deleted.
ST_DEFAULT, ST_IMPORTED, ST_TO_BE_DELETED = range(3)

# lacre_keys.confirmed is set to an empty string when a key is confirmed by the user.
CO_CONFIRMED = ''

_meta = sqlalchemy.MetaData()

LACRE_KEYS = sqlalchemy.Table('lacre_keys', _meta,
                              sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True, autoincrement='auto'),
                              sqlalchemy.Column('email', sqlalchemy.String(256), index=True),
                              # ASCII-armored key
                              sqlalchemy.Column('publickey', sqlalchemy.Text),
                              # Empty string means this key has been confirmed.
                              sqlalchemy.Column('confirm', sqlalchemy.String(32)),
                              # Status: see ST_* constants at the top of the file.
                              sqlalchemy.Column('status', sqlalchemy.Integer, nullable=False),
                              sqlalchemy.Column('time', sqlalchemy.DateTime))

LACRE_LOCKS = sqlalchemy.Table('lacre_locks', _meta,
                               sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True, nullable=False, autoincrement='auto'),
                               sqlalchemy.Column('ip', sqlalchemy.String(16)),
                               sqlalchemy.Column('time', sqlalchemy.Integer),
                               sqlalchemy.Column('action', sqlalchemy.String(16)),
                               sqlalchemy.Column('num', sqlalchemy.Integer),
                               )

LACRE_IDENTITIES = sqlalchemy.Table('lacre_identities', _meta,
                                    sqlalchemy.Column('email', sqlalchemy.String(256), index=True, nullable=False),
                                    # Key fingerprint
                                    sqlalchemy.Column('fingerprint', sqlalchemy.String(64), index=True, nullable=False))

def init_identities_table() -> sqlalchemy.Table:
    return LACRE_IDENTITIES

def init_locks_table() -> sqlalchemy.Table:
    return LACRE_LOCKS

def init_keys_table() -> sqlalchemy.Table:
    return LACRE_KEYS

def create_tables(engine):
    _meta.create_all(engine)

def table_metadata():
    return _meta
