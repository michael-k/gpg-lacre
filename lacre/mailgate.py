#
#	gpg-mailgate
#
#	This file is part of the gpg-mailgate source code.
#
#	gpg-mailgate is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	gpg-mailgate source code is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

from configparser import RawConfigParser
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import copy
import email
import email.message
import email.utils
import GnuPG
import os
import re
import smtplib
import sys
import syslog
import traceback
import time


# imports for S/MIME
from M2Crypto import BIO, Rand, SMIME, X509
from email.mime.message import MIMEMessage

import logging
import lacre
import lacre.text as text
import lacre.config as conf


LOG = logging.getLogger(__name__)

def gpg_encrypt( raw_message, recipients ):
	global LOG

	if not conf.config_item_set('gpg', 'keyhome'):
		LOG.error("No valid entry for gpg keyhome. Encryption aborted.")
		return recipients

	keys = GnuPG.public_keys( conf.get_item('gpg', 'keyhome') )
	for fingerprint in keys:
		keys[fingerprint] = sanitize_case_sense(keys[fingerprint])

	# This list will be filled with pairs (M, N), where M is the destination
	# address we're going to deliver the message to and N is the identity we're
	# going to encrypt it for.
	gpg_to = list()

	ungpg_to = list()

	enc_keymap_only = conf.config_item_equals('default', 'enc_keymap_only', 'yes')

	for to in recipients:

		# Check if recipient is in keymap
		if conf.config_item_set('enc_keymap', to):
			LOG.info("Encrypt keymap has key '%s'" % conf.get_item('enc_keymap', to) )
			# Check we've got a matching key!
			if conf.get_item('enc_keymap', to) in keys:
				gpg_to.append( (to, conf.get_item('enc_keymap', to)) )
				continue
			else:
				LOG.info("Key '%s' in encrypt keymap not found in keyring for email address '%s'." % (conf.get_item('enc_keymap', to), to))

		# Check if key in keychain is present
		if not enc_keymap_only:
			if to in keys.values():
				gpg_to.append( (to, to) )
				continue

            # If this is an address with a delimiter (i.e. "foo+bar@example.com"),
            # then strip whatever is found after the delimiter and try this address.
			(newto, topic) = text.parse_delimiter(to)
			if newto in keys.values():
				gpg_to.append((to, newto))

		# Check if there is a default key for the domain
		splitted_to = to.split('@')
		if len(splitted_to) > 1:
			domain = splitted_to[1]
			if conf.config_item_set('enc_domain_keymap', domain):
				LOG.info("Encrypt domain keymap has key '%s'" % conf.get_item('enc_domain_keymap', domain) )
				# Check we've got a matching key!
				if conf.get_item('enc_domain_keymap', domain) in keys:
					LOG.info("Using default domain key for recipient '%s'" % to)
					gpg_to.append( (to, conf.get_item('enc_domain_keymap', domain)) )
					continue
				else:
					LOG.info("Key '%s' in encrypt domain keymap not found in keyring for email address '%s'." % (conf.get_item('enc_domain_keymap', domain), to))
		
		# At this point no key has been found
		LOG.debug("Recipient (%s) not in PGP domain list for encrypting." % to)
		ungpg_to.append(to)

	if gpg_to:
		LOG.info("Encrypting email to: %s" % ' '.join( x[0] for x in gpg_to ))

		# Getting PGP style for recipient
		gpg_to_smtp_mime = list()
		gpg_to_cmdline_mime = list()

		gpg_to_smtp_inline = list()
		gpg_to_cmdline_inline = list()

		for rcpt in gpg_to:
			# Checking pre defined styles in settings first
			if conf.config_item_equals('pgp_style', rcpt[0], 'mime'):
				gpg_to_smtp_mime.append(rcpt[0])
				gpg_to_cmdline_mime.extend(rcpt[1].split(','))
			elif conf.config_item_equals('pgp_style', rcpt[0], 'inline'):
				gpg_to_smtp_inline.append(rcpt[0])
				gpg_to_cmdline_inline.extend(rcpt[1].split(','))
			else:
				# Log message only if an unknown style is defined
				if conf.config_item_set('pgp_style', rcpt[0]):
					LOG.debug("Style %s for recipient %s is not known. Use default as fallback." % (conf.get_item("pgp_style", rcpt[0]), rcpt[0]))

				# If no style is in settings defined for recipient, use default from settings
				if conf.config_item_equals('default', 'mime_conversion', 'yes'):
					gpg_to_smtp_mime.append(rcpt[0])
					gpg_to_cmdline_mime.extend(rcpt[1].split(','))
				else:
					gpg_to_smtp_inline.append(rcpt[0])
					gpg_to_cmdline_inline.extend(rcpt[1].split(','))

		if gpg_to_smtp_mime:
			# Encrypt mail with PGP/MIME
			raw_message_mime = copy.deepcopy(raw_message)

			if conf.config_item_equals('default', 'add_header', 'yes'):
				raw_message_mime['X-GPG-Mailgate'] = 'Encrypted by GPG Mailgate'

			if 'Content-Transfer-Encoding' in raw_message_mime:
				raw_message_mime.replace_header('Content-Transfer-Encoding', '8BIT')
			else:
				raw_message_mime['Content-Transfer-Encoding'] = '8BIT'

			encrypted_payloads = encrypt_all_payloads_mime( raw_message_mime, gpg_to_cmdline_mime )
			raw_message_mime.set_payload( encrypted_payloads )

			send_msg( raw_message_mime.as_string(), gpg_to_smtp_mime )

		if gpg_to_smtp_inline:
			# Encrypt mail with PGP/INLINE
			raw_message_inline = copy.deepcopy(raw_message)

			if conf.config_item_equals('default', 'add_header', 'yes'):
				raw_message_inline['X-GPG-Mailgate'] = 'Encrypted by GPG Mailgate'

			if 'Content-Transfer-Encoding' in raw_message_inline:
				raw_message_inline.replace_header('Content-Transfer-Encoding', '8BIT')
			else:
				raw_message_inline['Content-Transfer-Encoding'] = '8BIT'

			encrypted_payloads = encrypt_all_payloads_inline( raw_message_inline, gpg_to_cmdline_inline )
			raw_message_inline.set_payload( encrypted_payloads )

			send_msg( raw_message_inline.as_string(), gpg_to_smtp_inline )

	return ungpg_to

def encrypt_all_payloads_inline( message, gpg_to_cmdline ):

	# This breaks cascaded MIME messages. Blame PGP/INLINE.
	encrypted_payloads = list()
	if isinstance(message.get_payload(), str):
		return encrypt_payload( message, gpg_to_cmdline ).get_payload()

	for payload in message.get_payload():
		if( isinstance(payload.get_payload(), list) ):
			encrypted_payloads.extend( encrypt_all_payloads_inline( payload, gpg_to_cmdline ) )
		else:
			encrypted_payloads.append( encrypt_payload( payload, gpg_to_cmdline ) )

	return encrypted_payloads

def encrypt_all_payloads_mime( message, gpg_to_cmdline ):
	# Convert a plain text email into PGP/MIME attachment style.  Modeled after enigmail.
	pgp_ver_part = email.message.Message()
	pgp_ver_part.set_payload("Version: 1"+text.EOL)
	pgp_ver_part.set_type("application/pgp-encrypted")
	pgp_ver_part.set_param('PGP/MIME version identification', "", 'Content-Description' )

	encrypted_part = email.message.Message()
	encrypted_part.set_type("application/octet-stream")
	encrypted_part.set_param('name', "encrypted.asc")
	encrypted_part.set_param('OpenPGP encrypted message', "", 'Content-Description' )
	encrypted_part.set_param('inline', "",                'Content-Disposition' )
	encrypted_part.set_param('filename', "encrypted.asc", 'Content-Disposition' )

	if isinstance(message.get_payload(), str):
		# WTF!  It seems to swallow the first line.  Not sure why.  Perhaps
		# it's skipping an imaginary blank line someplace. (ie skipping a header)
		# Workaround it here by prepending a blank line.
		# This happens only on text only messages.
		additionalSubHeader=""
		encoding = sys.getdefaultencoding()
		if 'Content-Type' in message and not message['Content-Type'].startswith('multipart'):
			additionalSubHeader="Content-Type: "+message['Content-Type']+text.EOL
			(base, encoding) = text.parse_content_type(message['Content-Type'])
			LOG.debug(f"Identified encoding as {encoding}")
		encrypted_part.set_payload(additionalSubHeader+text.EOL +message.get_payload(decode=True).decode(encoding))
		check_nested = True
	else:
		processed_payloads = generate_message_from_payloads(message)
		encrypted_part.set_payload(processed_payloads.as_string())
		check_nested = False

	message.preamble = "This is an OpenPGP/MIME encrypted message (RFC 2440 and 3156)"

	# Use this just to generate a MIME boundary string.
	junk_msg = MIMEMultipart()
	junk_str = junk_msg.as_string()  # WTF!  Without this, get_boundary() will return 'None'!
	boundary = junk_msg.get_boundary()

	# This also modifies the boundary in the body of the message, ie it gets parsed.
	if 'Content-Type' in message:
		message.replace_header('Content-Type', f"multipart/encrypted; protocol=\"application/pgp-encrypted\"; boundary=\"{boundary}\""+text.EOL)
	else:
		message['Content-Type'] = f"multipart/encrypted; protocol=\"application/pgp-encrypted\"; boundary=\"{boundary}\""+text.EOL

	return [ pgp_ver_part, encrypt_payload(encrypted_part, gpg_to_cmdline, check_nested) ]

def encrypt_payload( payload, gpg_to_cmdline, check_nested = True ):
	global LOG

	raw_payload = payload.get_payload(decode=True)
	if check_nested and text.is_pgp_inline(raw_payload):
		LOG.debug("Message is already pgp encrypted. No nested encryption needed.")
		return payload

	# No check is needed for conf.get_item('gpg', 'keyhome') as this is already done in method gpg_encrypt
	gpg = GnuPG.GPGEncryptor( conf.get_item('gpg', 'keyhome'), gpg_to_cmdline, payload.get_content_charset() )
	gpg.update( raw_payload )
	encrypted_data, returncode = gpg.encrypt()
	LOG.debug("Return code from encryption=%d (0 indicates success)." % returncode)
	if returncode != 0:
		LOG.info("Encrytion failed with return code %d. Encryption aborted." % returncode)
		return payload

	payload.set_payload( encrypted_data )
	isAttachment = payload.get_param( 'attachment', None, 'Content-Disposition' ) is not None

	if isAttachment:
		filename = payload.get_filename()
		if filename:
			pgpFilename = filename + ".pgp"
			if not (payload.get('Content-Disposition') is None):
				payload.set_param( 'filename', pgpFilename, 'Content-Disposition' )
			if not (payload.get('Content-Type') is None) and not (payload.get_param( 'name' ) is None):
				payload.set_param( 'name', pgpFilename )
	if not (payload.get('Content-Transfer-Encoding') is None):
		payload.replace_header( 'Content-Transfer-Encoding', "7bit" )

	return payload

def smime_encrypt( raw_message, recipients ):
	global LOG
	global from_addr
	
	if not conf.config_item_set('smime', 'cert_path'):
		LOG.info("No valid path for S/MIME certs found in config file. S/MIME encryption aborted.")
		return recipients

	cert_path = conf.get_item('smime', 'cert_path')+"/"
	s = SMIME.SMIME()
	sk = X509.X509_Stack()
	smime_to = list()
	unsmime_to = list()

	for addr in recipients:
		cert_and_email = get_cert_for_email(addr, cert_path)

		if not (cert_and_email is None):
			(to_cert, normal_email) = cert_and_email
			LOG.debug("Found cert " + to_cert + " for " + addr + ": " + normal_email)
			smime_to.append(addr)
			x509 = X509.load_cert(to_cert, format=X509.FORMAT_PEM)
			sk.push(x509)
		else:
			unsmime_to.append(addr)

	if smime_to:
		s.set_x509_stack(sk)
		s.set_cipher(SMIME.Cipher('aes_192_cbc'))
		p7 = s.encrypt( BIO.MemoryBuffer( raw_message.as_string() ) )
		# Output p7 in mail-friendly format.
		out = BIO.MemoryBuffer()
		out.write('From: ' + from_addr + text.EOL)
		out.write('To: ' + raw_message['To'] + text.EOL)
		if raw_message['Cc']:
			out.write('Cc: ' + raw_message['Cc'] + text.EOL)
		if raw_message['Bcc']:
			out.write('Bcc: ' + raw_message['Bcc'] + text.EOL)
		if raw_message['Subject']:
			out.write('Subject: '+ raw_message['Subject'] + text.EOL)

		if conf.config_item_equals('default', 'add_header', 'yes'):
			out.write('X-GPG-Mailgate: Encrypted by GPG Mailgate' + text.EOL)

		s.write(out, p7)

		LOG.debug(f"Sending message from {from_addr} to {smime_to}")

		send_msg(out.read(), smime_to)
	if unsmime_to:
		LOG.debug(f"Unable to find valid S/MIME certificates for {unsmime_to}")

	return unsmime_to

def get_cert_for_email( to_addr, cert_path ):
	global LOG

	insensitive = conf.config_item_equals('default', 'mail_case_insensitive', 'yes')

	files_in_directory = os.listdir(cert_path)
	for filename in files_in_directory:
		file_path = os.path.join(cert_path, filename)
		if not os.path.isfile(file_path):
			continue

		if insensitive:
			if filename.casefold() == to_addr:
				return (file_path, to_addr)
		else:
			if filename == to_addr:
				return (file_path, to_addr)

	# support foo+ignore@bar.com -> foo@bar.com
	(fixed_up_email, topic) = text.parse_delimiter(to_addr)
	if topic is None:
		# delimiter not used
		return None
	else:
		LOG.debug(f"Looking up certificate for {fixed_up_email} after parsing {to_addr}")
		return get_cert_for_email(fixed_up_email, cert_path)

def sanitize_case_sense( address ):
	if conf.config_item_equals('default', 'mail_case_insensitive', 'yes'):
		address = address.lower()
	else:
		splitted_address = address.split('@')
		if len(splitted_address) > 1:
			address = splitted_address[0] + '@' + splitted_address[1].lower()

	return address

def generate_message_from_payloads( payloads, message = None ):
	if message == None:
		message = email.mime.multipart.MIMEMultipart(payloads.get_content_subtype())

	for payload in payloads.get_payload():
		if( isinstance(payload.get_payload(), list) ):
			message.attach(generate_message_from_payloads(payload))
		else:
			message.attach(payload)

	return message

def get_first_payload( payloads ):
	if payloads.is_multipart():
		return get_first_payload(payloads.get_payload(0))
	else:
		return payloads

def send_msg( message, recipients ):
	global LOG
	global from_addr

	recipients = [_f for _f in recipients if _f]
	if recipients:
		LOG.info(f"Sending email to: {recipients!r}")
		relay = (conf.get_item('relay', 'host'), int(conf.get_item('relay', 'port')))
		smtp = smtplib.SMTP(relay[0], relay[1])
		if conf.config_item_equals('relay', 'starttls', 'yes'):
			smtp.starttls()
		smtp.sendmail( from_addr, recipients, message )
	else:
		LOG.info("No recipient found")

def deliver_message( raw_message, from_address, to_addrs ):
	global LOG
	global from_addr

	# Ugly workaround to keep the code working without too many changes.
	from_addr = from_address

	recipients_left = [sanitize_case_sense(recipient) for recipient in to_addrs]

	# There is no need for nested encryption
	first_payload = get_first_payload(raw_message)
	if first_payload.get_content_type() == 'application/pkcs7-mime':
		LOG.debug("Message is already encrypted with S/MIME. Encryption aborted.")
		send_msg(raw_message.as_string(), recipients_left)
		return

	first_payload = first_payload.get_payload(decode=True)
	if text.is_pgp_inline(first_payload):
		LOG.debug("Message is already encrypted as PGP/INLINE. Encryption aborted.")
		send_msg(raw_message.as_string(), recipients_left)
		return

	if raw_message.get_content_type() == 'multipart/encrypted':
		LOG.debug("Message is already encrypted. Encryption aborted.")
		send_msg(raw_message.as_string(), recipients_left)
		return

	# Encrypt mails for recipients with known public PGP keys
	recipients_left = gpg_encrypt(raw_message, recipients_left)
	if not recipients_left:
		return

	# Encrypt mails for recipients with known S/MIME certificate
	recipients_left = smime_encrypt(raw_message, recipients_left)
	if not recipients_left:
		return

	# Send out mail to recipients which are left
	send_msg(raw_message.as_string(), recipients_left)

def exec_time_info(start_timestamp):
    elapsed_s = time.time() - start_timestamp
    process_t = time.process_time()
    return (elapsed_s, process_t)
