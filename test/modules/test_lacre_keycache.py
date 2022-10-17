from lacre.keyring import KeyCache

import unittest

class LacreKeyCacheTest(unittest.TestCase):
    def test_extend_keyring(self):
        kc = KeyCache({'FINGERPRINT': 'john.doe@example.com'})
        self.assertTrue('FINGERPRINT' in kc)

    def test_membership_methods(self):
        kc = KeyCache({
            'FINGERPRINT': 'alice@example.com',
            'OTHERPRINT': 'bob@example.com'
            })

        self.assertTrue('FINGERPRINT' in kc)
        self.assertFalse('FOOTPRINT' in kc)

        self.assertTrue(kc.has_email('bob@example.com'))
        self.assertFalse(kc.has_email('dave@example.com'))
