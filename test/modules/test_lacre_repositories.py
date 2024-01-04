"""Lacre identity and key repository tests."""

import unittest

import lacre.config as conf
import lacre.repositories as r
import lacre.dbschema as s

def ignore_sql(sql, *args, **kwargs):
    pass

class IdentityRepositoryTest(unittest.TestCase):

    def setUpClass():
        # required for init_engine to work
        conf.load_config()

    def test_freeze_identities(self):
        eng = r.init_engine('sqlite:///test/lacre.db')

        ir = r.IdentityRepository(engine=eng)
        identities = ir.freeze_identities()

        self.assertTrue(identities)
