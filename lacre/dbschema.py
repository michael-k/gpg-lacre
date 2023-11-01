"""Database schema for Lacre.

This definition includes:

- 'gpgmw_keys' -- temporary key storage, used by the frontend to submit keys and
  by webgate-cron script to import submitted keys.

- 'gpgmw_identities' -- identity catalogue, used by encryption logic to match
  emails with corresponding keys.
"""

import sqlalchemy

# Values for gpgmw_keys.status column:
ST_DEFAULT, ST_IMPORTED, ST_TO_BE_DELETED = range(3)

_meta = sqlalchemy.MetaData()

GPGMW_KEYS = sqlalchemy.Table('gpgmw_keys', _meta,
                              sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
                              sqlalchemy.Column('email', sqlalchemy.String(256)),
                              # ASCII-armored key
                              sqlalchemy.Column('publickey', sqlalchemy.Text),
                              sqlalchemy.Column('confirm', sqlalchemy.String(32)),
                              # Status: see ST_* constants at the top of the file.
                              sqlalchemy.Column('status', sqlalchemy.Integer),
                              sqlalchemy.Column('time', sqlalchemy.DateTime))

GPGMW_IDENTITIES = sqlalchemy.Table('gpgmw_identities', _meta,
                                    sqlalchemy.Column('email', sqlalchemy.String(256), index=True),
                                    # Key fingerprint
                                    sqlalchemy.Column('key_id', sqlalchemy.String(64), index=True))
