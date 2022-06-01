import lacre.text
import sys

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
