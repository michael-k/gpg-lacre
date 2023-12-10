import GnuPG
import logging

import unittest

class GnuPGUtilitiesTest(unittest.TestCase):
    def setUp(self):
        # Record GnuPG logs:
        logging.basicConfig(filename='test/logs/unittest.log', level=logging.DEBUG,
                            format='%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s')

    def test_build_default_command(self):
        cmd = GnuPG._build_command("test/keyhome")
        self.assertEqual(cmd, ["gpg", "--homedir", "test/keyhome"])

    def test_build_command_extended_with_args(self):
        cmd = GnuPG._build_command("test/keyhome", "--foo", "--bar")
        self.assertEqual(cmd, ["gpg", "--homedir", "test/keyhome", "--foo", "--bar"])

    def test_key_confirmation_with_matching_email(self):
        armored_key = self._load('test/keys/bob@disposlab.pub')
        matching_email = 'bob@disposlab'

        is_confirmed = GnuPG.confirm_key(armored_key, matching_email)
        self.assertTrue(is_confirmed)

    def test_key_confirmation_email_mismatch(self):
        armored_key = self._load('test/keys/bob@disposlab.pub')
        not_matching_email = 'lucy@disposlab'

        is_confirmed = GnuPG.confirm_key(armored_key, not_matching_email)
        self.assertFalse(is_confirmed)

    def test_key_listing(self):
        keys = GnuPG.public_keys('test/keyhome')

        known_identities = {
            '1CD245308F0963D038E88357973CF4D9387C44D7': 'alice@disposlab',
            '19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67': 'bob@disposlab',
            '530B1BB2D0CC7971648198BBA4774E507D3AF5BC': 'evan@disposlab'
            }

        self.assertDictEqual(keys, known_identities)

    def test_add_delete_key(self):
        self.assertDictEqual(GnuPG.public_keys('test/keyhome.other'), { })
        GnuPG.add_key('test/keyhome.other', self._load('test/keys/bob@disposlab.pub'))
        self.assertDictEqual(GnuPG.public_keys('test/keyhome.other'), {
            '19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67': 'bob@disposlab',
        })
        GnuPG.delete_key('test/keyhome.other', 'bob@disposlab')
        self.assertDictEqual(GnuPG.public_keys('test/keyhome.other'), { })

    def _load(self, filename):
        with open(filename) as f:
            return f.read()

    def test_extract_fingerprint(self):
        sample_in = '''fpr:::::::::1CD245308F0963D038E88357973CF4D9387C44D7:'''
        fpr = GnuPG._extract_fingerprint(sample_in)
        self.assertEqual(fpr, '1CD245308F0963D038E88357973CF4D9387C44D7')

    def test_parse_uid_line(self):
        sample_in = '''uid:e::::1624794010::C16E259AA1435947C6385B8160BC020B6C05EE18::alice@disposlab::::::::::0:'''
        uid = GnuPG._parse_uid_line(sample_in)
        self.assertEqual(uid, 'alice@disposlab')

    def test_parse_statusfd_key_expired(self):
        key_expired = b"""
[GNUPG:] KEYEXPIRED 1668272263
[GNUPG:] KEY_CONSIDERED XXXXXXXXXXXXX 0
[GNUPG:] INV_RECP 0 name@domain
[GNUPG:] FAILURE encrypt 1
"""

        result = GnuPG.parse_status(key_expired)
        self.assertEqual(result['issue'], 'key expired')
        self.assertEqual(result['recipient'], b'name@domain')
        self.assertEqual(result['cause'], 'Unknown')
        self.assertEqual(result['key'], b'XXXXXXXXXXXXX')

    def test_parse_statusfd_key_absent(self):
        non_specific_errors = b"""
[GNUPG:] INV_RECP 0 name@domain
[GNUPG:] FAILURE encrypt 1
"""

        result = GnuPG.parse_status(non_specific_errors)
        self.assertEqual(result['issue'], b'n/a')
        self.assertEqual(result['recipient'], b'name@domain')
        self.assertEqual(result['cause'], 'Unknown')
        self.assertEqual(result['key'], b'n/a')


if __name__ == '__main__':
    unittest.main()
