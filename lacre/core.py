#
# lacre
#
# This file is part of the lacre source code.
#
# lacre is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# lacre source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with lacre source code. If not, see <http://www.gnu.org/licenses/>.
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
import asyncio
from typing import Tuple

import logging
import lacre.text as text
import lacre.config as conf
import lacre.keyring as kcache
import lacre.recipients as recpt
import lacre.smime as smime
from lacre.transport import send_msg, register_sender, SendFrom
from lacre.mailop import KeepIntact, InlineOpenPGPEncrypt, MimeOpenPGPEncrypt, MailSerialisationException
from lacre.lazymessage import LazyMessage


LOG = logging.getLogger(__name__)


def _gpg_encrypt(raw_message, recipients):
    if not conf.config_item_set('gpg', 'keyhome'):
        LOG.error("No valid entry for gpg keyhome. Encryption aborted.")
        return recipients

    gpg_recipients, cleartext_recipients = \
        recpt.identify_gpg_recipients(recipients, kcache.freeze_and_load_keys())

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


def _sort_gpg_recipients(gpg_to) -> Tuple[recpt.RecipientList, recpt.RecipientList]:
    recipients_mime = list()
    keys_mime = list()

    recipients_inline = list()
    keys_inline = list()

    default_to_pgp_mime = conf.flag_enabled('default', 'mime_conversion')

    for rcpt in gpg_to:
        # Checking pre defined styles in settings first
        style = conf.PGPStyle.from_config('pgp_style', rcpt.email())
        if style is conf.PGPStyle.MIME:
            recipients_mime.append(rcpt.email())
            keys_mime.extend(rcpt.key().split(','))
        elif style is conf.PGPStyle.INLINE:
            recipients_inline.append(rcpt.email())
            keys_inline.extend(rcpt.key().split(','))
        else:
            # Log message only if an unknown style is defined
            if conf.config_item_set('pgp_style', rcpt.email()):
                LOG.debug("Style %s for recipient %s is not known. Use default as fallback.",
                          conf.get_item("pgp_style", rcpt.email()), rcpt.email())

            # If no style is in settings defined for recipient, use default from settings
            if default_to_pgp_mime:
                recipients_mime.append(rcpt.email())
                keys_mime.extend(rcpt.key().split(','))
            else:
                recipients_inline.append(rcpt.email())
                keys_inline.extend(rcpt.key().split(','))

    mime = recpt.RecipientList(recipients_mime, keys_mime)
    inline = recpt.RecipientList(recipients_inline, keys_inline)

    LOG.debug('Loaded recipients: MIME %s; Inline %s', repr(mime), repr(inline))

    return mime, inline


def _gpg_encrypt_copy(message: EmailMessage, keys, recipients, encrypt_f, lmessage: LazyMessage = None) -> EmailMessage:
    if lmessage:
        message = lmessage.get_message()

    msg_copy = copy.deepcopy(message)
    _customise_headers(msg_copy)
    encrypted_payloads = encrypt_f(msg_copy, keys)
    msg_copy.set_payload(encrypted_payloads)
    return msg_copy


def _gpg_encrypt_to_bytes(message: EmailMessage, keys, recipients, encrypt_f, lmessage) -> bytes:
    msg_copy = _gpg_encrypt_copy(message, keys, recipients, encrypt_f, lmessage)
    try:
        return msg_copy.as_bytes(policy=SMTPUTF8)
    except IndexError as ie:
        raise MailSerialisationException(ie)


def _gpg_encrypt_to_str(message: EmailMessage, keys, recipients, encrypt_f) -> str:
    msg_copy = _gpg_encrypt_copy(message, keys, recipients, encrypt_f)
    return msg_copy.as_string(policy=SMTPUTF8)


def _gpg_encrypt_and_deliver(message: EmailMessage, keys, recipients, encrypt_f):
    out = _gpg_encrypt_to_str(message, keys, recipients, encrypt_f)
    send_msg(out, recipients)


def _customise_headers(message: EmailMessage):
    if conf.flag_enabled('default', 'add_header'):
        message['X-Lacre'] = 'Encrypted by Lacre'


def _encrypt_all_payloads_inline(message: EmailMessage, gpg_to_cmdline, lmessage: LazyMessage = None):
    if lmessage:
        message = lmessage.get_message()

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


def _encrypt_all_payloads_mime(message: EmailMessage, gpg_to_cmdline, lmessage: LazyMessage = None):
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

    if lmessage:
        message = lmessage.get_message()

    message.preamble = "This is an OpenPGP/MIME encrypted message (RFC 2440 and 3156)"

    boundary = _make_boundary()

    if isinstance(message.get_payload(), str):
        LOG.debug('Rewrapping a flat, text-only message')
        wrapped_payload = _rewrap_payload(message)
        encrypted_part.set_payload(wrapped_payload.as_string())

        _set_type_and_boundary(message, boundary)

        check_nested = True
    else:
        processed_payloads = _generate_message_from_payloads(message)
        encrypted_part.set_payload(processed_payloads.as_string())

        _set_type_and_boundary(message, boundary)

        check_nested = False

    return [pgp_ver_part, _encrypt_payload(encrypted_part, gpg_to_cmdline, check_nested)]


def _rewrap_payload(message: EmailMessage, lmessage: LazyMessage = None) -> MIMEPart:
    # In PGP/MIME (RFC 3156), the payload has to be a valid MIME entity.  In
    # other words, we need to wrap text/* message's payload in a new MIME
    # entity.

    wrapper = MIMEPart(policy=SMTPUTF8)
    if lmessage:
        message = lmessage.get_message()
    content = message.get_content()
    wrapper.set_content(content)

    wrapper.set_type(message.get_content_type())

    # Copy all Content-Type parameters.
    for (pname, pvalue) in message.get_params(failobj=list()):
        # Skip MIME type that's also returned by get_params().
        if not '/' in pname:
            wrapper.set_param(pname, pvalue)

    return wrapper


def _make_boundary():
    junk_msg = MIMEMultipart()
    # XXX See EmailTest.test_boundary_generated_after_as_string_call.
    _ = junk_msg.as_string()
    return junk_msg.get_boundary()


def _set_type_and_boundary(message: EmailMessage, boundary):
    message.set_type('multipart/encrypted')
    message.set_param('protocol', 'application/pgp-encrypted')
    message.set_param('boundary', boundary)


def _encrypt_payload(payload: EmailMessage, recipients, check_nested=True, lmessage: LazyMessage = None, **kwargs):
    if lmessage:
        payload = lmessage.get_message()
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


def _recode(m: EmailMessage):
    payload = m.get_payload()
    m.set_content(payload)


def failover_delivery(lmessage: LazyMessage, recipients, from_address):
    """Try delivering message just one last time."""
    LOG.debug('Failover delivery')

    send = SendFrom(from_address)
    orig = lmessage.get_original_content()

    send(orig, recipients)


def _is_encrypted(raw_message: EmailMessage, lmessage: LazyMessage = None):
    if lmessage:
        raw_message = lmessage.get_message()
    if raw_message.get_content_type() == 'multipart/encrypted':
        return True

    first_part = _get_first_payload(raw_message)
    if first_part.get_content_type() == 'application/pkcs7-mime':
        return True

    return text.is_message_pgp_inline(first_part)


def delivery_plan(recipients, message: EmailMessage, key_cache: kcache.KeyCache, lmessage: LazyMessage = None):
    """Generate a sequence of delivery strategies."""
    if lmessage:
        message = lmessage.get_message()

    if _is_encrypted(message):
        LOG.debug('Message is already encrypted: %s', message)
        return [KeepIntact(recipients)]

    gpg_recipients, cleartext_recipients = recpt.identify_gpg_recipients(recipients, key_cache)

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


def deliver_message(message: LazyMessage, from_address, to_addrs):
    """Send RAW_MESSAGE to all TO_ADDRS using the best encryption method available."""
    # Ugly workaround to keep the code working without too many changes.
    register_sender(from_address)

    raw_message = message.get_message()

    sanitize = text.choose_sanitizer(conf.get_item('default', 'mail_case_insensitive'))
    recipients_left = [sanitize(recipient) for recipient in to_addrs]

    send = SendFrom(from_address)

    # There is no need for nested encryption
    LOG.debug("Seeing if it's already encrypted")
    if _is_encrypted(raw_message):
        LOG.debug("Message is already encrypted. Encryption aborted.")
        send(raw_message.as_string(), recipients_left)
        return

    # Encrypt mails for recipients with known public PGP keys
    LOG.debug("Encrypting with OpenPGP")
    recipients_left = _gpg_encrypt(raw_message, recipients_left)
    if not recipients_left:
        return

    # Encrypt mails for recipients with known S/MIME certificate
    LOG.debug("Encrypting with S/MIME")
    recipients_left = smime.encrypt(raw_message, recipients_left, from_address)
    if not recipients_left:
        return

    # Send out mail to recipients which are left
    LOG.debug("Sending the rest as cleartext")
    send(raw_message.as_bytes(policy=SMTPUTF8), recipients_left)
