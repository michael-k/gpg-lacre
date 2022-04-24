import sys
import sqlalchemy
from sqlalchemy.sql import insert

def define_db_schema():
	meta = sqlalchemy.MetaData()

	gpgmw_keys = sqlalchemy.Table('gpgmw_keys', meta,
								  sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
								  sqlalchemy.Column('email', sqlalchemy.String(256)),
								  sqlalchemy.Column('publickey', sqlalchemy.Text),
								  sqlalchemy.Column('confirm', sqlalchemy.String(32)),
								  sqlalchemy.Column('status', sqlalchemy.Integer),
								  sqlalchemy.Column('time', sqlalchemy.DateTime))

	return (meta, gpgmw_keys)

if len(sys.argv) != 2:
	print("ERROR: output database missing")
	sys.exit(1)

(meta, gpgmw_keys) = define_db_schema()

dbname = sys.argv[1]
test_db = sqlalchemy.create_engine(f"sqlite:///{dbname}")

# Initialise the schema
meta.create_all(test_db)

conn = test_db.connect()

# Populate the database with dummy data
conn.execute(gpgmw_keys.insert(), [
	{"id": 1, "email": "alice@disposlab", "publickey": "-----BEGIN PGP PUBLIC KEY BLOCK-----\
\
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\
pw==\
=Tbwz\
-----END PGP PUBLIC KEY BLOCK-----\
", "status": 0, "confirm": "", "time": None},
	{"id": 2, "email": "bob@disposlab",   "publickey": "-----BEGIN PGP PUBLIC KEY BLOCK-----\
\
mDMEYdTFkRYJKwYBBAHaRw8BAQdA2tgdP1pMt3cv3XAW7ov5AFn74mMZvyTksp9Q\
eO1PkpK0GkJvYiBGb29iYXIgPGJvYkBkaXNwb3NsYWI+iJYEExYIAD4WIQQZz0tH\
7MnEevqE1L2W85/aDjG7ZwUCYdTFkQIbAwUJA8JnAAULCQgHAgYVCgkICwIEFgID\
AQIeAQIXgAAKCRCW85/aDjG7ZxVnAP49t7BU2H+/WCpa3fCAlMEcik82sU4p+U9D\
pMsbjawwYgEA1SbA5CF835cMjoEufy1h+2M4T9gI/0X2lk8OAtwwggm4OARh1MXg\
EgorBgEEAZdVAQUBAQdAUVNKx2OsGtNdRsnl3J/uv6obkUC0KcO4ikdRs+iejlMD\
AQgHiHgEGBYIACAWIQQZz0tH7MnEevqE1L2W85/aDjG7ZwUCYdTF4AIbDAAKCRCW\
85/aDjG7Z039APwLGP5ibqCC9yIr4YVbdWff1Ch+2C91MR2ObF93Up9+ogD8D2zd\
OjjB6xRD0Q2FN+alsNGCtdutAs18AZ5l33RMzws=\
=wWoq\
-----END PGP PUBLIC KEY BLOCK-----\
", "status": 0, "confirm": "", "time": None},
	{"id": 3, "email": "cecil@lacre.io", "publickey": "RUBBISH", "status": 0, "confirm": "", "time": None}
	])
