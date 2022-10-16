from lacre.keyring import KeyCache

import unittest

class LacreKeyCacheTest(unittest.TestCase):
    def test_extend_keyring(self):
        kc = KeyCache()

        self.assertFalse('FINGERPRINT' in kc)

        kc.extend_keyring({'FINGERPRINT': 'john.doe@example.com'})

        self.assertTrue('FINGERPRINT' in kc)

    def test_membership_methods(self):
        kc = KeyCache()

        kc.extend_keyring({
            'FINGERPRINT': 'alice@example.com',
            'OTHERPRINT': 'bob@example.com'
            })

        self.assertTrue('FINGERPRINT' in kc)
        self.assertTrue(kc.has_email('bob@example.com'))

    def test_keyring_replacement(self):
        kc = KeyCache()

        kc.extend_keyring({
            'FINGERPRINT': 'alice@example.com',
            'OTHERPRINT': 'bob@example.com'
            })

        self.assertTrue('FINGERPRINT' in kc)

        kc.replace_keyring({
            'FOO': 'foo@example.com',
            'BAR': 'bar@example.com'
            })

        self.assertFalse('FINGERPRINT' in kc)
        self.assertTrue('FOO' in kc)
