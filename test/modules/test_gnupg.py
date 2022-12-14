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

    def _load(self, filename):
        with open(filename) as f:
            return f.read()


if __name__ == '__main__':
    unittest.main()
