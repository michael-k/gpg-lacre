from M2Crypto import BIO
import unittest

class M2CryptoBioMemoryBufferTest(unittest.TestCase):
	def test_memory_buffer_write_str(self):
		mb = BIO.MemoryBuffer()
		mb.write("Foo")
		mb.close()
		self.assertEqual(len(mb), 3)

	def test_memory_buffer_write_bytes(self):
		mb = BIO.MemoryBuffer()
		mb.write(b"Foo")
		mb.close()
		self.assertEqual(len(mb), 3)
