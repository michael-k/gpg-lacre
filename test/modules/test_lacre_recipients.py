import lacre.recipients

import unittest


class RecipientListTest(unittest.TestCase):
    def test_addition(self):
        a_list = lacre.recipients.RecipientList()
        a_list += lacre.recipients.GpgRecipient(
            'alice@disposlab',
            '1CD245308F0963D038E88357973CF4D9387C44D7')

        emails = [x for x in a_list.emails()]
        keys = [x for x in a_list.keys()]

        self.assertSequenceEqual(emails, ['alice@disposlab'])
        self.assertSequenceEqual(keys, ['1CD245308F0963D038E88357973CF4D9387C44D7'])
