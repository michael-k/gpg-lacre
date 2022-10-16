"""Lacre's actual mail-delivery module.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

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

from email.mime.multipart import MIMEMultipart
import copy
import email
import email.message
import email.utils
import GnuPG
import os
import smtplib
import sys
import time

# imports for S/MIME
from M2Crypto import BIO, SMIME, X509

import logging
import lacre.text as text
import lacre.config as conf
import lacre.keyring as kcache
from lacre.mailop import KeepIntact, InlineOpenPGPEncrypt, MimeOpenPGPEncrypt


LOG = logging.getLogger(__name__)


def _gpg_encrypt(raw_message, recipients):
    if not conf.config_item_set('gpg', 'keyhome'):
        LOG.error("No valid entry for gpg keyhome. Encryption aborted.")
        return recipients

    gpg_to, ungpg_to = _identify_gpg_recipients(recipients, _load_keys())

    LOG.info(f"Got addresses: gpg_to={gpg_to!r}, ungpg_to={ungpg_to!r}")

    if gpg_to:
        LOG.info("Encrypting email to: %s" % ' '.join(x.email() for x in gpg_to))

        gpg_to_smtp_mime, gpg_to_cmdline_mime, \
            gpg_to_smtp_inline, gpg_to_cmdline_inline = \
            _sort_gpg_recipients(gpg_to)

        if gpg_to_smtp_mime:
            # Encrypt mail with PGP/MIME
            _gpg_encrypt_and_deliver(raw_message,
                                     gpg_to_cmdline_mime, gpg_to_smtp_mime,
                                     _encrypt_all_payloads_mime)

        if gpg_to_smtp_inline:
            # Encrypt mail with PGP/INLINE
            _gpg_encrypt_and_deliver(raw_message,
                                     gpg_to_cmdline_inline, gpg_to_smtp_inline,
                                     _encrypt_all_payloads_inline)

    LOG.info(f"Not processed emails: {ungpg_to}")
    return ungpg_to


def _sort_gpg_recipients(gpg_to):
    gpg_to_smtp_mime = list()
    gpg_to_cmdline_mime = list()

    gpg_to_smtp_inline = list()
    gpg_to_cmdline_inline = list()

    default_to_pgp_mime = conf.config_item_equals('default', 'mime_conversion', 'yes')

    for rcpt in gpg_to:
        # Checking pre defined styles in settings first
        if conf.config_item_equals('pgp_style', rcpt.email(), 'mime'):
            gpg_to_smtp_mime.append(rcpt.email())
            gpg_to_cmdline_mime.extend(rcpt.key().split(','))
        elif conf.config_item_equals('pgp_style', rcpt.email(), 'inline'):
            gpg_to_smtp_inline.append(rcpt.email())
            gpg_to_cmdline_inline.extend(rcpt.key().split(','))
        else:
            # Log message only if an unknown style is defined
            if conf.config_item_set('pgp_style', rcpt.email()):
                LOG.debug("Style %s for recipient %s is not known. Use default as fallback."
                          % (conf.get_item("pgp_style", rcpt.email()), rcpt.email()))

            # If no style is in settings defined for recipient, use default from settings
            if default_to_pgp_mime:
                gpg_to_smtp_mime.append(rcpt.email())
                gpg_to_cmdline_mime.extend(rcpt.key().split(','))
            else:
                gpg_to_smtp_inline.append(rcpt.email())
                gpg_to_cmdline_inline.extend(rcpt.key().split(','))

    return gpg_to_smtp_mime, gpg_to_cmdline_mime, gpg_to_smtp_inline, gpg_to_cmdline_inline


def _gpg_encrypt_and_return(message, cmdline, to, encrypt_f) -> str:
    msg_copy = copy.deepcopy(message)
    _customise_headers(msg_copy)
    encrypted_payloads = encrypt_f(msg_copy, cmdline)
    msg_copy.set_payload(encrypted_payloads)
    return msg_copy.as_string()


def _gpg_encrypt_and_deliver(message, cmdline, to, encrypt_f):
    out = _gpg_encrypt_and_return(message, cmdline, to, encrypt_f)
    send_msg(out, to)


def _customise_headers(msg_copy):
    if conf.config_item_equals('default', 'add_header', 'yes'):
        msg_copy['X-GPG-Mailgate'] = 'Encrypted by GPG Mailgate'

    if 'Content-Transfer-Encoding' in msg_copy:
        msg_copy.replace_header('Content-Transfer-Encoding', '8BIT')
    else:
        msg_copy['Content-Transfer-Encoding'] = '8BIT'


def _load_keys():
    """Return a map from a key's fingerprint to email address."""
    keys = kcache.KeyCache()
    keys.load_keyring_from(conf.get_item('gpg', 'keyhome'))
    return keys


class GpgRecipient:
    """A tuple-like object that contains GPG recipient data."""

    def __init__(self, left, right):
        """Initialise a tuple-like object that contains GPG recipient data."""
        self._left = left
        self._right = right

    def __getitem__(self, index):
        """Pretend this object is a tuple by returning an indexed tuple element."""
        if index == 0:
            return self._left
        elif index == 1:
            return self._right
        else:
            raise IndexError()

    def __repr__(self):
        """Return textual representation of this GPG Recipient."""
        return f"GpgRecipient({self._left!r}, {self._right!r})"

    def email(self):
        """Return this recipient's email address."""
        return self._left

    def key(self):
        """Return this recipient's key ID."""
        return self._right


def _identify_gpg_recipients(recipients, keys: kcache.KeyCache):
    # This list will be filled with pairs (M, N), where M is the destination
    # address we're going to deliver the message to and N is the identity we're
    # going to encrypt it for.
    gpg_to = list()

    # This will be the list of recipients that haven't provided us with their
    # public keys.
    ungpg_to = list()

    # In "strict mode", only keys included in configuration are used to encrypt
    # email.
    strict_mode = conf.strict_mode()

    # GnuPG keys found in our keyring.

    LOG.info(f'Processisng recipients: {recipients!r}; keys: {keys!r}')
    for to in recipients:
        LOG.info(f"At to={to!r}")
        own_key = _try_configured_key(to, keys)
        if own_key is not None:
            gpg_to.append(GpgRecipient(own_key[0], own_key[1]))
            continue

        direct_key = _try_direct_key_lookup(to, keys, strict_mode)
        if direct_key is not None:
            gpg_to.append(GpgRecipient(direct_key[0], direct_key[1]))
            continue

        domain_key = _try_configured_domain_key(to, keys)
        if domain_key is not None:
            gpg_to.append(GpgRecipient(domain_key[0], domain_key[1]))
            continue

        ungpg_to.append(to)

    LOG.debug(f'Collected recipients;  GPG: {gpg_to};  UnGPG: {ungpg_to}')
    return gpg_to, ungpg_to


def _find_key(recipient, keys, strict_mode):
    own_key = _try_configured_key(recipient, keys)
    if own_key is not None:
        return own_key

    direct_key = _try_direct_key_lookup(recipient, keys, strict_mode)
    if direct_key is not None:
        return direct_key

    domain_key = _try_configured_domain_key(recipient, keys)
    if domain_key is not None:
        return domain_key

    return None


def _try_configured_key(recipient, keys):
    if conf.config_item_set('enc_keymap', recipient):
        key = conf.get_item('enc_keymap', recipient)
        if key in keys:
            LOG.debug(f"Found key {key} configured for {recipient}")
            return (recipient, key)

    LOG.debug(f"No configured key found for {recipient}")
    return None


def _try_direct_key_lookup(recipient, keys, strict_mode):
    if strict_mode:
        return None

    if keys.has_email(recipient):
        LOG.info(f"Found key for {recipient}")
        return recipient, recipient

    (newto, topic) = text.parse_delimiter(recipient)
    if keys.has_email(newto):
        LOG.info(f"Found key for {newto}, stripped {recipient}")
        return recipient, newto

    return None


def _try_configured_domain_key(recipient, keys):
    parts = recipient.split('@')
    if len(parts) != 2:
        return None

    domain = parts[1]
    if conf.config_item_set('enc_domain_keymap', domain):
        domain_key = conf.get_item('enc_domain_keymap', domain)
        if domain_key in keys:
            LOG.debug(f"Found domain key {domain_key} for {recipient}")
            return recipient, domain_key

    LOG.debug(f"No domain key for {recipient}")
    return None


def _encrypt_all_payloads_inline(message, gpg_to_cmdline):

    # This breaks cascaded MIME messages. Blame PGP/INLINE.
    encrypted_payloads = list()
    if isinstance(message.get_payload(), str):
        return _encrypt_payload(message, gpg_to_cmdline).get_payload()

    for payload in message.get_payload():
        if(isinstance(payload.get_payload(), list)):
            encrypted_payloads.extend(_encrypt_all_payloads_inline(payload, gpg_to_cmdline))
        else:
            encrypted_payloads.append(_encrypt_payload(payload, gpg_to_cmdline))

    return encrypted_payloads


def _encrypt_all_payloads_mime(message, gpg_to_cmdline):
    # Convert a plain text email into PGP/MIME attachment style.  Modeled after enigmail.
    pgp_ver_part = email.message.Message()
    pgp_ver_part.set_payload("Version: 1"+text.EOL)
    pgp_ver_part.set_type("application/pgp-encrypted")
    pgp_ver_part.set_param('PGP/MIME version identification', "", 'Content-Description')

    encrypted_part = email.message.Message()
    encrypted_part.set_type("application/octet-stream")
    encrypted_part.set_param('name', "encrypted.asc")
    encrypted_part.set_param('OpenPGP encrypted message', "", 'Content-Description')
    encrypted_part.set_param('inline', "",                'Content-Disposition')
    encrypted_part.set_param('filename', "encrypted.asc", 'Content-Disposition')

    if isinstance(message.get_payload(), str):
        # WTF!  It seems to swallow the first line.  Not sure why.  Perhaps
        # it's skipping an imaginary blank line someplace. (ie skipping a header)
        # Workaround it here by prepending a blank line.
        # This happens only on text only messages.
        additionalSubHeader = ""
        encoding = sys.getdefaultencoding()
        if 'Content-Type' in message and not message['Content-Type'].startswith('multipart'):
            additionalSubHeader = "Content-Type: " + message['Content-Type'] + text.EOL
            (base, encoding) = text.parse_content_type(message['Content-Type'])
            LOG.debug(f"Identified encoding as {encoding}")
        encrypted_part.set_payload(additionalSubHeader+text.EOL + message.get_payload(decode=True).decode(encoding))
        check_nested = True
    else:
        processed_payloads = _generate_message_from_payloads(message)
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

    return [pgp_ver_part, _encrypt_payload(encrypted_part, gpg_to_cmdline, check_nested)]


def _encrypt_payload(payload, gpg_to_cmdline, check_nested=True):
    raw_payload = payload.get_payload(decode=True)
    if check_nested and text.is_pgp_inline(raw_payload):
        LOG.debug("Message is already pgp encrypted. No nested encryption needed.")
        return payload

    # No check is needed for conf.get_item('gpg', 'keyhome') as this is already
    # done in method gpg_encrypt
    gpg = GnuPG.GPGEncryptor(conf.get_item('gpg', 'keyhome'), gpg_to_cmdline,
                             payload.get_content_charset())
    gpg.update(raw_payload)
    encrypted_data, returncode = gpg.encrypt()
    LOG.debug("Return code from encryption=%d (0 indicates success)." % returncode)
    if returncode != 0:
        LOG.info("Encrytion failed with return code %d. Encryption aborted." % returncode)
        return payload

    payload.set_payload(encrypted_data)
    isAttachment = payload.get_param('attachment', None, 'Content-Disposition') is not None

    if isAttachment:
        filename = payload.get_filename()
        if filename:
            pgpFilename = filename + ".pgp"
            if not (payload.get('Content-Disposition') is None):
                payload.set_param('filename', pgpFilename, 'Content-Disposition')
            if not (payload.get('Content-Type') is None) and not (payload.get_param('name') is None):
                payload.set_param('name', pgpFilename)
    if not (payload.get('Content-Transfer-Encoding') is None):
        payload.replace_header('Content-Transfer-Encoding', "7bit")

    return payload


def _smime_encrypt(raw_message, recipients):
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
        cert_and_email = _get_cert_for_email(addr[0], cert_path)

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
        p7 = s.encrypt(BIO.MemoryBuffer(raw_message.as_string()))
        # Output p7 in mail-friendly format.
        out = BIO.MemoryBuffer()
        out.write('From: ' + from_addr + text.EOL)
        out.write('To: ' + raw_message['To'] + text.EOL)
        if raw_message['Cc']:
            out.write('Cc: ' + raw_message['Cc'] + text.EOL)
        if raw_message['Bcc']:
            out.write('Bcc: ' + raw_message['Bcc'] + text.EOL)
        if raw_message['Subject']:
            out.write('Subject: ' + raw_message['Subject'] + text.EOL)

        if conf.config_item_equals('default', 'add_header', 'yes'):
            out.write('X-GPG-Mailgate: Encrypted by GPG Mailgate' + text.EOL)

        s.write(out, p7)

        LOG.debug(f"Sending message from {from_addr} to {smime_to}")

        send_msg(out.read(), smime_to)
    if unsmime_to:
        LOG.debug(f"Unable to find valid S/MIME certificates for {unsmime_to}")

    return unsmime_to


def _get_cert_for_email(to_addr, cert_path):
    insensitive = conf.config_item_equals('default', 'mail_case_insensitive', 'yes')

    LOG.info(f'Retrieving certificate for {to_addr!r} from {cert_path!r}, sensitivity={insensitive!r}')

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
    LOG.info(f"An email with topic? {to_addr}")
    (fixed_up_email, topic) = text.parse_delimiter(to_addr)
    LOG.info(f'Got {fixed_up_email!r} and {topic!r}')
    if topic is None:
        # delimiter not used
        LOG.info('Topic not found')
        return None
    else:
        LOG.info(f"Looking up certificate for {fixed_up_email} after parsing {to_addr}")
        return _get_cert_for_email(fixed_up_email, cert_path)


def _generate_message_from_payloads(payloads, message=None):
    if message is None:
        message = email.mime.multipart.MIMEMultipart(payloads.get_content_subtype())

    for payload in payloads.get_payload():
        if(isinstance(payload.get_payload(), list)):
            message.attach(_generate_message_from_payloads(payload))
        else:
            message.attach(payload)

    return message


def _get_first_payload(payloads):
    if payloads.is_multipart():
        return _get_first_payload(payloads.get_payload(0))
    else:
        return payloads


def send_msg(message: str, recipients, fromaddr=None):
    """Send MESSAGE to RECIPIENTS to the mail relay."""
    global from_addr

    if fromaddr is not None:
        from_addr = fromaddr

    recipients = [_f for _f in recipients if _f]
    if recipients:
        LOG.info(f"Sending email to: {recipients!r}")
        relay = conf.relay_params()
        smtp = smtplib.SMTP(relay[0], relay[1])
        if conf.flag_enabled('relay', 'starttls'):
            smtp.starttls()
        smtp.sendmail(from_addr, recipients, message)
    else:
        LOG.info("No recipient found")


def _is_encrypted(raw_message):
    if raw_message.get_content_type() == 'multipart/encrypted':
        return True

    first_part = _get_first_payload(raw_message)
    if first_part.get_content_type() == 'application/pkcs7-mime':
        return True

    first_payload = first_part.get_payload(decode=True)
    return text.is_pgp_inline(first_payload)


def delivery_plan(recipients, key_cache: kcache.KeyCache):
    """Generate a sequence of delivery strategies."""
    gpg_to, ungpg_to = _identify_gpg_recipients(recipients, key_cache)

    gpg_mime_to, gpg_mime_cmd, gpg_inline_to, gpg_inline_cmd = \
        _sort_gpg_recipients(gpg_to)

    keyhome = conf.get_item('gpg', 'keyhome')

    plan = []
    if gpg_mime_to:
        plan.append(MimeOpenPGPEncrypt(gpg_mime_to, gpg_mime_cmd, keyhome))
    if gpg_inline_to:
        plan.append(InlineOpenPGPEncrypt(gpg_inline_to, gpg_inline_cmd, keyhome))
    if ungpg_to:
        plan.append(KeepIntact(ungpg_to))

    return plan


def deliver_message(raw_message: email.message.Message, from_address, to_addrs):
    """Send RAW_MESSAGE to all TO_ADDRS using the best encryption method available."""
    global from_addr

    # Ugly workaround to keep the code working without too many changes.
    from_addr = from_address

    recipients_left = [text.sanitize_case_sense(recipient) for recipient in to_addrs]

    # There is no need for nested encryption
    LOG.debug("Seeing if it's already encrypted")
    if _is_encrypted(raw_message):
        LOG.debug("Message is already encrypted. Encryption aborted.")
        send_msg(raw_message.as_string(), recipients_left)
        return

    # Encrypt mails for recipients with known public PGP keys
    LOG.debug("Encrypting with OpenPGP")
    recipients_left = _gpg_encrypt(raw_message, recipients_left)
    if not recipients_left:
        return

    # Encrypt mails for recipients with known S/MIME certificate
    LOG.debug("Encrypting with S/MIME")
    recipients_left = _smime_encrypt(raw_message, recipients_left)
    if not recipients_left:
        return

    # Send out mail to recipients which are left
    LOG.debug("Sending the rest as text/plain")
    send_msg(raw_message.as_string(), recipients_left)


def exec_time_info(start_timestamp):
    """Calculate time since the given timestamp."""
    elapsed_s = time.time() - start_timestamp
    process_t = time.process_time()
    return (elapsed_s, process_t)
