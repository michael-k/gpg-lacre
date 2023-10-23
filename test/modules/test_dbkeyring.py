"""Tests for lacre.dbkeyring."""

import lacre.dbkeyring as dbk

import unittest

class LacreDbKeyringTest(unittest.TestCase):
    def test_load_keys(self):
        db_url = 'sqlite:///test/lacre.db'
        schema = dbk.KeyRingSchema()
        db = dbk.DatabaseKeyRing(db_url, schema)

        identities = db.freeze_identities()

        self.assertTrue('1CD245308F0963D038E88357973CF4D9387C44D7' in identities)
        self.assertTrue(identities.has_email('alice@disposlab'))
