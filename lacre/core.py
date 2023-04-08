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

"""Lacre's actual mail-delivery module.

IMPORTANT: This module has to be loaded _after_ initialisation of the logging
module.
"""

from email.mime.multipart import MIMEMultipart
import copy
import email
from email.message import EmailMessage, MIMEPart
import email.utils
from email.policy import SMTPUTF8
import GnuPG
import os
import smtplib
import asyncio
from typing import Tuple

# imports for S/MIME
from M2Crypto import BIO, SMIME, X509

import logging
import lacre.text as text
import lacre.config as conf
import lacre.keyring as kcache
from lacre.mailop import KeepIntact, InlineOpenPGPEncrypt, MimeOpenPGPEncrypt


LOG = logging.getLogger(__name__)


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


class RecipientList:
    """Encalsulates two lists of recipients.

    First list contains addresses, the second - GPG identities.
    """

    def __init__(self, recipients=[], keys=[]):
        """Initialise lists of recipients and identities."""
        self._recipients = [GpgRecipient(email, key) for (email, key) in zip(recipients, keys)]

    def emails(self):
        """Return list of recipients."""
        LOG.debug('Recipient emails from: %s', self._recipients)
        return [r.email() for r in self._recipients]

    def keys(self):
        """Return list of GPG identities."""
        LOG.debug('Recipient keys from: %s', self._recipients)
        return [r.key() for r in self._recipients]

    def __iadd__(self, recipient: GpgRecipient):
        """Append a recipient."""
        LOG.debug('Adding %s to %s', recipient, self._recipients)
        self._recipients.append(recipient)
        LOG.debug('Added; got: %s', self._recipients)
        return self

    def __len__(self):
        """Provide len().

        With this method, it is possible to write code like:

        rl = RecipientList()
        if rl:
            # do something
        """
        return len(self._recipients)


def _gpg_encrypt(raw_message, recipients):
    if not conf.config_item_set('gpg', 'keyhome'):
        LOG.error("No valid entry for gpg keyhome. Encryption aborted.")
        return recipients

    gpg_recipients, cleartext_recipients = _identify_gpg_recipients(recipients, _load_keys())

    LOG.info(f"Got addresses: gpg_to={gpg_recipients!r}, ungpg_to={cleartext_recipients!r}")

    if gpg_recipients:
        LOG.info("Encrypting email to: %s", gpg_recipients)

        mime, inline = _sort_gpg_recipients(gpg_recipients)

        if mime:
            # Encrypt mail with PGP/MIME
            _gpg_encrypt_and_deliver(raw_message,
                                     mime.keys(), mime.emails(),
                                     _encrypt_all_payloads_mime)

        if inline:
            # Encrypt mail with PGP/INLINE
            _gpg_encrypt_and_deliver(raw_message,
                                     inline.keys(), inline.emails(),
                                     _encrypt_all_payloads_inline)

    LOG.info('Not processed emails: %s', cleartext_recipients)
    return cleartext_recipients


def _sort_gpg_recipients(gpg_to) -> Tuple[RecipientList, RecipientList]:
    mime = RecipientList()
    inline = RecipientList()

    recipients_mime = list()
    keys_mime = list()

    recipients_inline = list()
    keys_inline = list()

    default_to_pgp_mime = conf.flag_enabled('default', 'mime_conversion')

    for rcpt in gpg_to:
        # Checking pre defined styles in settings first
        if conf.config_item_equals('pgp_style', rcpt.email(), 'mime'):
            recipients_mime.append(rcpt.email())
            keys_mime.extend(rcpt.key().split(','))
            mime += rcpt
        elif conf.config_item_equals('pgp_style', rcpt.email(), 'inline'):
            recipients_inline.append(rcpt.email())
            keys_inline.extend(rcpt.key().split(','))
            inline += rcpt
        else:
            # Log message only if an unknown style is defined
            if conf.config_item_set('pgp_style', rcpt.email()):
                LOG.debug("Style %s for recipient %s is not known. Use default as fallback."
                          % (conf.get_item("pgp_style", rcpt.email()), rcpt.email()))

            # If no style is in settings defined for recipient, use default from settings
            if default_to_pgp_mime:
                recipients_mime.append(rcpt.email())
                keys_mime.extend(rcpt.key().split(','))
                mime += rcpt
            else:
                recipients_inline.append(rcpt.email())
                keys_inline.extend(rcpt.key().split(','))
                inline += rcpt

    mime = RecipientList(recipients_mime, keys_mime)
    inline = RecipientList(recipients_inline, keys_inline)

    LOG.debug('Loaded recipients: MIME %s; Inline %s', repr(mime), repr(inline))

    return mime, inline


def _gpg_encrypt_copy(message: EmailMessage, keys, recipients, encrypt_f):
    msg_copy = copy.deepcopy(message)
    _customise_headers(msg_copy)
    encrypted_payloads = encrypt_f(msg_copy, keys)
    msg_copy.set_payload(encrypted_payloads)
    return msg_copy


def _gpg_encrypt_to_bytes(message: EmailMessage, keys, recipients, encrypt_f) -> bytes:
    msg_copy = _gpg_encrypt_copy(message, keys, recipients, encrypt_f)
    return msg_copy.as_bytes(policy=SMTPUTF8)


def _gpg_encrypt_to_str(message: EmailMessage, keys, recipients, encrypt_f) -> str:
    msg_copy = _gpg_encrypt_copy(message, keys, recipients, encrypt_f)
    return msg_copy.as_string(policy=SMTPUTF8)


def _gpg_encrypt_and_deliver(message: EmailMessage, keys, recipients, encrypt_f):
    out = _gpg_encrypt_to_str(message, keys, recipients, encrypt_f)
    send_msg(out, recipients)


def _customise_headers(message: EmailMessage):
    if conf.config_item_equals('default', 'add_header', 'yes'):
        message['X-GPG-Mailgate'] = 'Encrypted by GPG Mailgate'

    if 'Content-Transfer-Encoding' in message:
        message.replace_header('Content-Transfer-Encoding', '8BIT')
    else:
        message['Content-Transfer-Encoding'] = '8BIT'


def _load_keys():
    """Return a map from a key's fingerprint to email address."""
    keyring = kcache.KeyRing(conf.get_item('gpg', 'keyhome'))
    return asyncio.run(keyring.freeze_identities())


def _identify_gpg_recipients(recipients, keys: kcache.KeyCache):
    # This list will be filled with pairs (M, N), where M is the destination
    # address we're going to deliver the message to and N is the identity we're
    # going to encrypt it for.
    gpg_recipients = list()

    # This will be the list of recipients that haven't provided us with their
    # public keys.
    cleartext_recipients = list()

    # In "strict mode", only keys included in configuration are used to encrypt
    # email.
    strict_mode = conf.strict_mode()

    # GnuPG keys found in our keyring.

    for to in recipients:
        own_key = _try_configured_key(to, keys)
        if own_key is not None:
            gpg_recipients.append(GpgRecipient(own_key[0], own_key[1]))
            continue

        direct_key = _try_direct_key_lookup(to, keys, strict_mode)
        if direct_key is not None:
            gpg_recipients.append(GpgRecipient(direct_key[0], direct_key[1]))
            continue

        domain_key = _try_configured_domain_key(to, keys)
        if domain_key is not None:
            gpg_recipients.append(GpgRecipient(domain_key[0], domain_key[1]))
            continue

        cleartext_recipients.append(to)

    LOG.debug('Collected recipients; GPG: %s; cleartext: %s', gpg_recipients, cleartext_recipients)
    return gpg_recipients, cleartext_recipients


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


def _encrypt_all_payloads_inline(message: EmailMessage, gpg_to_cmdline):

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


def _encrypt_all_payloads_mime(message: EmailMessage, gpg_to_cmdline):
    # Convert a plain text email into PGP/MIME attachment style.  Modeled after enigmail.
    pgp_ver_part = MIMEPart()
    pgp_ver_part.set_content('Version: 1' + text.EOL_S)
    pgp_ver_part.set_type("application/pgp-encrypted")
    pgp_ver_part.set_param('PGP/MIME version identification', "", 'Content-Description')

    encrypted_part = MIMEPart()
    encrypted_part.set_type("application/octet-stream")
    encrypted_part.set_param('name', "encrypted.asc")
    encrypted_part.set_param('OpenPGP encrypted message', "", 'Content-Description')
    encrypted_part.set_param('inline', "",                'Content-Disposition')
    encrypted_part.set_param('filename', "encrypted.asc", 'Content-Disposition')

    message.preamble = "This is an OpenPGP/MIME encrypted message (RFC 2440 and 3156)"

    boundary = _make_boundary()

    if isinstance(message.get_payload(), str):
        wrapped_payload = _rewrap_payload(message)
        encrypted_part.set_payload(wrapped_payload.as_string())

        _set_type_and_boundary(message, boundary)

        return [pgp_ver_part, _encrypt_payload(encrypted_part, gpg_to_cmdline, True)]
    else:
        processed_payloads = _generate_message_from_payloads(message)
        encrypted_part.set_payload(processed_payloads.as_string())

        _set_type_and_boundary(message, boundary)

        return [pgp_ver_part, _encrypt_payload(encrypted_part, gpg_to_cmdline, False)]


def _rewrap_payload(message: EmailMessage) -> MIMEPart:
    # In PGP/MIME (RFC 3156), the payload has to be a valid MIME entity.  In
    # other words, we need to wrap text/plain message's payload in a new MIME
    # entity.

    pld = MIMEPart()
    pld.set_type(message.get_content_type())
    pld.set_content(message.get_content())

    # Make sure all Content-Type parameters are included.
    for (k, v) in message.get_params():
        pld.set_param(k, v)

    return pld


def _make_boundary():
    junk_msg = MIMEMultipart()
    # XXX See EmailTest.test_boundary_generated_after_as_string_call.
    _ = junk_msg.as_string()
    return junk_msg.get_boundary()


def _set_type_and_boundary(message: EmailMessage, boundary):
    message.set_type('multipart/encrypted')
    message.set_param('protocol', 'application/pgp-encrypted')
    message.set_param('boundary', boundary)


def _encrypt_payload(payload: EmailMessage, recipients, check_nested=True, **kwargs):
    raw_payload = payload.get_payload(decode=True)
    LOG.debug('About to encrypt raw payload: %s', raw_payload)
    LOG.debug('Original message: %s', payload)

    if check_nested and text.is_payload_pgp_inline(raw_payload):
        LOG.debug("Message is already pgp encrypted. No nested encryption needed.")
        return payload

    gpg = _make_encryptor(raw_payload, recipients)

    gpg.update(raw_payload)
    encrypted_data, exit_code = gpg.encrypt()

    payload.set_payload(encrypted_data)
    isAttachment = payload.get_param('attachment', None, 'Content-Disposition') is not None

    if isAttachment:
        _append_gpg_extension(payload)
    if not (payload.get('Content-Transfer-Encoding') is None):
        payload.replace_header('Content-Transfer-Encoding', "7bit")

    return payload


def _make_encryptor(raw_data, recipients):
    # No check is needed for conf.get_item('gpg', 'keyhome') as this is already
    # done in method gpg_encrypt
    keyhome = conf.get_item('gpg', 'keyhome')

    if isinstance(raw_data, str):
        return GnuPG.GPGEncryptor(keyhome, recipients, 'utf-8')
    else:
        return GnuPG.GPGEncryptor(keyhome, recipients)


def _append_gpg_extension(attachment):
    filename = attachment.get_filename()
    if not filename:
        return

    pgpFilename = filename + ".pgp"

    # Attachment name can come from one of two places: Content-Disposition or
    # Content-Type header, hence the two cases below.

    if not (attachment.get('Content-Disposition') is None):
        attachment.set_param('filename', pgpFilename, 'Content-Disposition')

    if not (attachment.get('Content-Type') is None) and not (attachment.get_param('name') is None):
        attachment.set_param('name', pgpFilename)


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
        cert_and_email = _get_cert_for_email(addr, cert_path)

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
        out.write('From: ' + from_addr + text.EOL_S)
        out.write('To: ' + raw_message['To'] + text.EOL_S)
        if raw_message['Cc']:
            out.write('Cc: ' + raw_message['Cc'] + text.EOL_S)
        if raw_message['Bcc']:
            out.write('Bcc: ' + raw_message['Bcc'] + text.EOL_S)
        if raw_message['Subject']:
            out.write('Subject: ' + raw_message['Subject'] + text.EOL_S)

        if conf.config_item_equals('default', 'add_header', 'yes'):
            out.write('X-GPG-Mailgate: Encrypted by GPG Mailgate' + text.EOL_S)

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


def send_msg_bytes(message: bytes, recipients, fromaddr=None):
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


def _recode(m: EmailMessage):
    payload = m.get_payload()
    m.set_content(payload)


def failover_delivery(message: EmailMessage, recipients):
    """Try delivering message just one last time."""
    LOG.debug('Failover delivery')

    if message.get_content_maintype() == 'text':
        LOG.debug('Flat text message, adjusting coding')
        _recode(message)
        b = message.as_bytes(policy=SMTPUTF8)
        send_msg_bytes(b, recipients)
    elif message.get_content_maintype() == 'multipart':
        LOG.debug('Multipart message, adjusting coding of text entities')
        for part in message.iter_parts():
            if part.get_content_maintype() == 'text':
                _recode(part)
        b = message.as_bytes(policy=SMTPUTF8)
        send_msg_bytes(b, recipients)
    else:
        LOG.warning('No failover strategy, giving up')


def _is_encrypted(raw_message: EmailMessage):
    if raw_message.get_content_type() == 'multipart/encrypted':
        return True

    first_part = _get_first_payload(raw_message)
    if first_part.get_content_type() == 'application/pkcs7-mime':
        return True

    return text.is_message_pgp_inline(first_part)


def delivery_plan(recipients, message: EmailMessage, key_cache: kcache.KeyCache):
    """Generate a sequence of delivery strategies."""
    if _is_encrypted(message):
        LOG.debug('Message is already encrypted: %s', message)
        return [KeepIntact(recipients)]

    gpg_recipients, cleartext_recipients = _identify_gpg_recipients(recipients, key_cache)

    mime, inline = _sort_gpg_recipients(gpg_recipients)

    keyhome = conf.get_item('gpg', 'keyhome')

    plan = []
    if mime:
        plan.append(MimeOpenPGPEncrypt(mime.emails(), mime.keys(), keyhome))
    if inline:
        plan.append(InlineOpenPGPEncrypt(inline.emails(), inline.keys(), keyhome))
    if cleartext_recipients:
        plan.append(KeepIntact(cleartext_recipients))

    return plan


def deliver_message(raw_message: EmailMessage, from_address, to_addrs):
    """Send RAW_MESSAGE to all TO_ADDRS using the best encryption method available."""
    global from_addr

    # Ugly workaround to keep the code working without too many changes.
    from_addr = from_address

    sanitize = text.choose_sanitizer(conf.get_item('default', 'mail_case_insensitive'))
    recipients_left = [sanitize(recipient) for recipient in to_addrs]

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
