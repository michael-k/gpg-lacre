import sys

PGP_INLINE_BEGIN = b"-----BEGIN PGP MESSAGE-----"
PGP_INLINE_END = b"-----END PGP MESSAGE-----"

def parse_content_type(content_type):
	split_at = content_type.find(';')
	if split_at < 0:
		return (content_type, sys.getdefaultencoding())
	second_part = content_type[split_at+1 : ].strip()
	if second_part.startswith('charset'):
		return (content_type[0 : split_at], second_part[second_part.index('=') + 1 : ].strip())
	else:
		return (content_type[0 : split_at], sys.getdefaultencoding())

def is_pgp_inline(payload):
	"""Finds out if the payload (bytes) contains PGP/INLINE markers."""
	return PGP_INLINE_BEGIN in payload and PGP_INLINE_END in payload
