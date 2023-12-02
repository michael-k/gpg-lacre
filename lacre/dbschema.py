"""Database schema for Lacre.

This definition includes:

- 'lacre_keys' -- temporary key storage, used by the frontend to submit keys and
  by webgate-cron script to import submitted keys.

- 'lacre_identities' -- identity catalogue, used by encryption logic to match
  emails with corresponding keys.
"""

import sqlalchemy

# Values for lacre_keys.status column:
ST_DEFAULT, ST_IMPORTED, ST_TO_BE_DELETED = range(3)

_meta = sqlalchemy.MetaData()

LACRE_KEYS = sqlalchemy.Table('lacre_keys', _meta,
                              sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
                              sqlalchemy.Column('email', sqlalchemy.String(256)),
                              # ASCII-armored key
                              sqlalchemy.Column('publickey', sqlalchemy.Text),
                              sqlalchemy.Column('confirm', sqlalchemy.String(32)),
                              # Status: see ST_* constants at the top of the file.
                              sqlalchemy.Column('status', sqlalchemy.Integer),
                              sqlalchemy.Column('time', sqlalchemy.DateTime))

LACRE_IDENTITIES = sqlalchemy.Table('lacre_identities', _meta,
                                    sqlalchemy.Column('email', sqlalchemy.String(256), index=True),
                                    # Key fingerprint
                                    sqlalchemy.Column('fingerprint', sqlalchemy.String(64), index=True))

def init_identities_table() -> sqlalchemy.Table:
    return LACRE_IDENTITIES

def table_metadata():
    return _meta
