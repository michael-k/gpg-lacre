import lacre.text
import sys
from email import message_from_binary_file
from email.message import EmailMessage
from email.policy import SMTPUTF8

import unittest

class LacreTextTest(unittest.TestCase):
    def test_parse_content_type_without_charset(self):
        (mtype, mcharset) = lacre.text.parse_content_type('text/plain')
        self.assertEqual(mtype, 'text/plain')
        self.assertEqual(mcharset, sys.getdefaultencoding())

    def test_parse_content_type_with_charset(self):
        (mtype, mcharset) = lacre.text.parse_content_type('text/plain; charset="UTF-8"')
        self.assertEqual(mtype, 'text/plain')
        self.assertEqual(mcharset, '"UTF-8"')

    def test_parse_content_type_with_other_attributes(self):
        (mtype, mcharset) = lacre.text.parse_content_type('text/plain; some-param="Some Value"')
        self.assertEqual(mtype, 'text/plain')
        self.assertEqual(mcharset, sys.getdefaultencoding())

    def test_parse_content_type_with_several_attributes(self):
        (mtype, mcharset) = lacre.text.parse_content_type('text/plain; charset="UTF-8"; some-param="Some Value"')
        self.assertEqual(mtype, 'text/plain')
        self.assertEqual(mcharset, '"UTF-8"')

    def test_parse_email_without_delimiter(self):
        addr = "Some.Name@example.com"
        (addr2, topic) = lacre.text.parse_delimiter(addr)
        self.assertEqual(addr2, "Some.Name@example.com")
        self.assertEqual(topic, None)

    def test_parse_email_with_delimiter(self):
        addr = "Some.Name+some-topic@example.com"
        (addr2, topic) = lacre.text.parse_delimiter(addr)
        self.assertEqual(addr2, "Some.Name@example.com")
        self.assertEqual(topic, "some-topic")

    def test_pgp_inline_recognised(self):
        msg = None
        with open('test/msgin/ed2ed.msg', 'rb') as f:
            msg = message_from_binary_file(f, policy=SMTPUTF8)

        body = msg.get_payload()

        self.assertIn(lacre.text.PGP_BEGIN_S, body)
        self.assertIn(lacre.text.PGP_END_S, body)
        self.assertTrue(lacre.text.is_payload_pgp_inline(body))

    def test_pgp_marker_mentioned(self):
        msg = None
        with open('test/msgin/with-markers2clear.msg', 'rb') as f:
            msg = message_from_binary_file(f, policy=SMTPUTF8)

        body = msg.get_payload()

        self.assertFalse(lacre.text.is_payload_pgp_inline(body))
