import lacre.core
from email.message import EmailMessage

import unittest


class LacreCoreTest(unittest.TestCase):
    def test_attachment_handling(self):
        m = EmailMessage()
        m.set_payload('This is a payload')
        m.set_param('attachment', '', 'Content-Disposition')
        m.set_param('filename', 'foo', 'Content-Disposition')

        lacre.core._append_gpg_extension(m)

        self.assertEqual(m.get_filename(), 'foo.pgp')

    def test_attachment_handling_2(self):
        m = EmailMessage()
        m.set_payload('This is a payload')
        m.set_param('attachment', '', 'Content-Disposition')
        m.set_param('name', 'quux', 'Content-Type')

        lacre.core._append_gpg_extension(m)

        self.assertEqual(m.get_filename(), 'quux.pgp')

    def test_payload_wrapping(self):
        m = EmailMessage()
        m.set_payload('This is a payload.\r\n'
                      + '\r\n'
                      + 'It has two paragraphs.\r\n')
        m['Subject'] = 'Source message'
        m.set_type('text/plain')
        m.set_param('charset', 'utf-8')

        rewrapped = lacre.core._rewrap_payload(m)

        self.assertFalse('Subject' in rewrapped,
                         'only content and content-type should be copied')
        self.assertEqual(rewrapped.get_content_type(), 'text/plain',
                         'rewrapped part should have initial message\'s content-type')
