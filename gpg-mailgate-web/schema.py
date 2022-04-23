import sqlalchemy

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

(meta, gpgmw_keys) = define_db_schema()

test_db = sqlalchemy.create_engine("sqlite:///test.db")

meta.create_all(test_db)
