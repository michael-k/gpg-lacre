#
# gpg-mailgate
#
# This file is part of the gpg-mailgate source code.
#
# gpg-mailgate is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gpg-mailgate source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

"""Unit-tests as contracts for external dependencies.

Unit tests defined here are our contracts for the dependencies used by Lacre.
Since not all software is documented thoroughly, they are also a form of
documentation.
"""

import email
import email.mime.multipart
import unittest
from configparser import RawConfigParser


class EmailParsingTest(unittest.TestCase):
    """This test serves as a package contract and documentation of its behaviour."""

    def test_message_from_bytes_produces_message_with_str_headers(self):
        rawmsg = b"From: alice@lacre.io\r\n" \
          + b"To: bob@lacre.io\r\n" \
          + b"Subject: Test message\r\n" \
          + b"\r\n" \
          + b"Test message from Alice to Bob.\r\n"

        parsed = email.message_from_bytes(rawmsg)

        self.assertEqual(parsed["From"], "alice@lacre.io")
        self.assertEqual(parsed["To"], "bob@lacre.io")
        self.assertEqual(parsed["Subject"], "Test message")

    def test_bytes_message_payload_decoded_produces_bytes(self):
        rawmsg = b"From: alice@lacre.io\r\n" \
          + b"To: bob@lacre.io\r\n" \
          + b"Subject: Test message\r\n" \
          + b"\r\n" \
          + b"Test message from Alice to Bob.\r\n"

        parsed = email.message_from_bytes(rawmsg)

        self.assertEqual(parsed.get_payload(), "Test message from Alice to Bob.\r\n")
        self.assertEqual(parsed.get_payload(decode=True), b"Test message from Alice to Bob.\r\n")

    def test_message_from_string_produces_message_with_str_headers(self):
        rawmsg = "From: alice@lacre.io\r\n" \
          + "To: bob@lacre.io\r\n" \
          + "Subject: Test message\r\n" \
          + "\r\n" \
          + "Test message from Alice to Bob.\r\n"

        parsed = email.message_from_string(rawmsg)

        self.assertEqual(parsed["From"], "alice@lacre.io")
        self.assertEqual(parsed["To"], "bob@lacre.io")
        self.assertEqual(parsed["Subject"], "Test message")

    def test_str_message_payload_decoded_produces_bytes(self):
        rawmsg = "From: alice@lacre.io\r\n" \
          + "To: bob@lacre.io\r\n" \
          + "Subject: Test message\r\n" \
          + "\r\n" \
          + "Test message from Alice to Bob.\r\n"

        parsed = email.message_from_string(rawmsg)

        self.assertEqual(parsed.get_payload(), "Test message from Alice to Bob.\r\n")
        self.assertEqual(parsed.get_payload(decode=True), b"Test message from Alice to Bob.\r\n")


class EmailTest(unittest.TestCase):
    def test_boundary_generated_after_as_string_call(self):
        mp = email.mime.multipart.MIMEMultipart()
        self.assertTrue(mp.get_boundary() is None)
        _ = mp.as_string()
        self.assertFalse(mp.get_boundary() is None)


class RawConfigParserTest(unittest.TestCase):
    def test_config_parser_returns_str(self):
        cp = RawConfigParser()
        cp.read("test/sample.ini")
        self.assertEqual(cp.get("foo", "bar"), "quux")
        self.assertEqual(cp.get("foo", "baz"), "14")


if __name__ == '__main__':
    unittest.main()
