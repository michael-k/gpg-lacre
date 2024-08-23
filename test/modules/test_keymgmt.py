import unittest

import datetime
import lacre.keymgmt as km

class KeyManagementUtilitiesTest(unittest.TestCase):
    def test_expiry_date_calculation(self):
        ts = datetime.datetime(2024, 1, 1, 12, 0)
        exp = km.calculate_expiry_date(ts)
        self.assertEqual(exp, datetime.datetime(2024, 1, 1, 11, 0))
