import GnuPG

import unittest

class GnuPGUtilitiesTest(unittest.TestCase):
    def test_build_default_command(self):
        cmd = GnuPG._build_command("test/keyhome")
        self.assertEqual(cmd, ["gpg", "--homedir", "test/keyhome"])

    def test_build_command_extended_with_args(self):
        cmd = GnuPG._build_command("test/keyhome", "--foo", "--bar")
        self.assertEqual(cmd, ["gpg", "--homedir", "test/keyhome", "--foo", "--bar"])

    def test_key_confirmation_with_matching_email(self):
        armored_key = self._load('test/keys/bob@disposlab')
        matching_email = 'bob@disposlab'

        is_confirmed = GnuPG.confirm_key(armored_key, matching_email)
        self.assertTrue(is_confirmed)

    def test_key_confirmation_email_mismatch(self):
        armored_key = self._load('test/keys/bob@disposlab')
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
        self.assertDictEqual(GnuPG.public_keys('/tmp'), { })
        GnuPG.add_key('/tmp', self._load('test/keys/bob@disposlab.pub'))
        self.assertDictEqual(GnuPG.public_keys('/tmp'), {
            '19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67': 'bob@disposlab',
        })
        GnuPG.delete_key('/tmp', 'bob@disposlab')
        self.assertDictEqual(GnuPG.public_keys('/tmp'), { })

    def _load(self, filename):
        with open(filename) as f:
            return f.read()

    def test_parse_statusfd_key_expired(self):
        key_expired = b"""
[GNUPG:] KEYEXPIRED 1668272263
[GNUPG:] KEY_CONSIDERED XXXXXXXXXXXXX 0
[GNUPG:] INV_RECP 0 name@domain
[GNUPG:] FAILURE encrypt 1
"""
        result = GnuPG.parse_status(key_expired)
        self.assertEqual(result['issue'], b'KEYEXPIRED')
        self.assertEqual(result['recipient'], b'name@domain')
        self.assertEqual(result['cause'], 'No specific reason given')


if __name__ == '__main__':
    unittest.main()
