import sys

# The standard way to encode line-ending in email:
EOL = "\r\n"

PGP_INLINE_BEGIN = b"-----BEGIN PGP MESSAGE-----"
PGP_INLINE_END = b"-----END PGP MESSAGE-----"

def parse_content_type(content_type):
	parts = [p.strip() for p in content_type.split(';')]
	if len(parts) == 1:
		# No additional attributes provided.  Use default encoding.
		return (content_type, sys.getdefaultencoding())

	# At least one attribute provided.  Find out if any of them is named
	# 'charset' and if so, use it.
	ctype = parts[0]
	encoding = [p for p in parts[1:] if p.startswith('charset=') ]
	if encoding:
		eq_idx = encoding[0].index('=')
		return (ctype, encoding[0][eq_idx+1:])
	else:
		return (ctype, sys.getdefaultencoding())

def is_pgp_inline(payload):
	"""Finds out if the payload (bytes) contains PGP/INLINE markers."""
	return PGP_INLINE_BEGIN in payload and PGP_INLINE_END in payload
