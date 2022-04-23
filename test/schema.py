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
	{"id": 1, "email": "alice@lacre.io", "publickey": "PUBLICKEY1", "status": 0, "confirm": "", "time": None},
	{"id": 2, "email": "bob@lacre.io",   "publickey": "PUBLICKEY2", "status": 0, "confirm": "", "time": None},
	{"id": 3, "email": "cecil@lacre.io", "publickey": "PUBLICKEY3", "status": 0, "confirm": "", "time": None}
	])
