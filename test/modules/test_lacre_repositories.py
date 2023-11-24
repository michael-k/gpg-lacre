"""Lacre identity and key repository tests."""

import unittest

import lacre.repositories as r
import lacre.dbschema as s

class IdentityRepositoryTest(unittest.TestCase):

    def test_x(self):
        ir = r.IdentityRepository(s.GPGMW_IDENTITIES, db_url='sqlite:///test/lacre.db')
        identities = ir.freeze_identities()

        self.assertTrue(identities)
