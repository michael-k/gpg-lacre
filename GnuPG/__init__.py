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

"""GnuPG wrapper module."""

import os
import os.path
import subprocess
import shutil
import random
import string
import sys
import logging
import re
import tempfile
from email.utils import parseaddr


LINE_FINGERPRINT = 'fpr'
LINE_USER_ID = 'uid'
LINE_PUBLIC_KEY = 'pub'

POS_FINGERPRINT = 9
POS_UID = 9

LOG = logging.getLogger(__name__)

RX_CONFIRM = re.compile(br'key "([^"]+)" imported')


class EncryptionException(Exception):
    """Represents a failure to encrypt a payload."""

    def __init__(self, issue: str, recipient: str, cause: str):
        """Initialise an exception."""
        self._issue = issue
        self._recipient = recipient
        self._cause = cause

    def __str__(self):
        """Return human-readable string representation."""
        return f"issue: {self._issue}; to: {self._recipient}; cause: {self._cause}"


def _build_command(key_home, *args, **kwargs):
    cmd = ["gpg", '--homedir', key_home]
    cmd.extend(args)
    return cmd


def public_keys(keyhome, *, key_id=None):
    """List public keys from keyring KEYHOME."""
    cmd = _build_command(keyhome, '--list-keys', '--with-colons')
    if key_id is not None:
        cmd.append(key_id)

    p = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()

    keys = dict()
    collected = set()

    fingerprint = None
    email = None

    for line in p.stdout.readlines():
        line = line.decode(sys.getdefaultencoding())

        if line[0:3] == LINE_PUBLIC_KEY:
            # New identity has started, reset state.
            fingerprint = None
            email = None

        if line[0:3] == LINE_FINGERPRINT and not fingerprint:
            fingerprint = _extract_fingerprint(line)

        if line[0:3] == LINE_USER_ID:
            email = _parse_uid_line(line)

        if fingerprint and email and not email in collected:
            keys[fingerprint] = email
            collected.add(email)
            fingerprint = None
            email = None

    p.stdout.close()
    p.stderr.close()
    return keys


def _extract_fingerprint(line):
    fpr_line = line.split(':')
    if len(fpr_line) <= POS_FINGERPRINT:
        return None
    else:
        return fpr_line[POS_FINGERPRINT]


def _parse_uid_line(line: str):
    userid_line = line.split(':')
    if len(userid_line) <= POS_UID:
        return None
    else:
        (_, email) = parseaddr(userid_line[POS_UID])
        return email


def _to_bytes(s) -> bytes:
    if isinstance(s, str):
        return bytes(s, sys.getdefaultencoding())
    else:
        return s


# Confirms a key has a given email address by importing it into a temporary
# keyring.  If this operation succeeds and produces a message mentioning the
# expected email, a key is confirmed.
def confirm_key(content, email: str):
    """Verify that the key CONTENT is assigned to identity EMAIL."""
    content = _to_bytes(content)
    expected_email = email.lower()

    tmpkeyhome = tempfile.mkdtemp()

    result = _import_key(tmpkeyhome, content)
    confirmed = False

    for line in result.splitlines():
        found = RX_CONFIRM.search(line)
        if found:
            (_, extracted_email) = parseaddr(found.group(1).decode())
            confirmed = (extracted_email == expected_email)

    # cleanup
    shutil.rmtree(tmpkeyhome)

    return confirmed


def _import_key(keyhome, content):
    content = _to_bytes(content)

    # Ensure we get expected output regardless of the system locale.
    localized_env = os.environ.copy()
    localized_env["LANG"] = "C"

    p = subprocess.Popen(_build_command(keyhome, '--import', '--batch'), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=localized_env)
    output = p.communicate(input=content)[1]
    p.wait()

    return output


# adds a key and ensures it has the given email address
def add_key(keyhome, content):
    """Register new key CONTENT in the keyring KEYHOME."""
    output = _import_key(keyhome, content)

    email = None
    for line in output.splitlines():
        found = RX_CONFIRM.search(line)
        if found:
            (_, extracted_email) = parseaddr(found.group(1).decode())
            email = extracted_email

    # Find imported key to get its fingerprint
    imported = public_keys(keyhome, key_id=email)

    if len(imported.keys()) == 1:
        fingerprint = list(imported.keys())[0]
        return fingerprint, imported[fingerprint]
    else:
        return None, None


def delete_key(keyhome, email):
    """Remove key assigned to identity EMAIL from keyring KEYHOME."""
    result = parseaddr(email)

    if result[1]:
        # delete all keys matching this email address
        p = subprocess.Popen(_build_command(keyhome, '--delete-key', '--batch', '--yes', result[1]), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.communicate()
        p.wait()
        return True

    LOG.warn('Failed to parse email before deleting key: %s', email)
    return False


class GPGEncryptor:
    """A wrapper for 'gpg -e' command."""

    def __init__(self, keyhome, recipients=None, charset=None):
        """Initialise the wrapper."""
        self._keyhome = keyhome
        self._message = None
        self._recipients = list()
        self._charset = charset
        if recipients is not None:
            self._recipients.extend(recipients)

    def update(self, message):
        """Append MESSAGE to buffer about to be encrypted."""
        if self._message is None:
            self._message = message
        else:
            self._message += message

    def encrypt(self):
        """Feed GnuPG with the message."""
        p = self._popen()
        encdata, err = p.communicate(input=self._message)
        if p.returncode != 0:
            LOG.debug('Errors: %s', err)
            details = parse_status(err)
            raise EncryptionException(details['issue'], details['recipient'], details['cause'])
        return (encdata, p.returncode)

    def _popen(self):
        if self._charset:
            return subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    encoding=self._charset)
        else:
            return subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)

    def _command(self):
        cmd = _build_command(self._keyhome,
                             "--trust-model", "always",
                             "--status-fd", "2",
                             "--batch",
                             "--yes",
                             "--pgp7",
                             "--no-secmem-warning",
                             "-a", "-e")

        # add recipients
        for recipient in self._recipients:
            cmd.append("-r")
            cmd.append(recipient)

        # add on the charset, if set
        if self._charset:
            cmd.append("--comment")
            cmd.append('Charset: ' + self._charset)

        LOG.debug('Built command: %s', cmd)
        return cmd


class GPGDecryptor:
    """A wrapper for 'gpg -d' command."""

    def __init__(self, keyhome):
        """Initialise the wrapper."""
        self._keyhome = keyhome
        self._message = ''

    def update(self, message):
        """Append encrypted content to be decrypted."""
        self._message += message

    def decrypt(self):
        """Decrypt the message."""
        p = subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        decdata = p.communicate(input=self._message)[0]
        return (decdata, p.returncode)

    def _command(self):
        return _build_command(self._keyhome, "--trust-model", "always", "--batch", "--yes", "--no-secmem-warning", "-a", "-d")


STATUS_FD_PREFIX = b'[GNUPG:] '
STATUS_FD_PREFIX_LEN = len(STATUS_FD_PREFIX)

KEY_EXPIRED       = b'KEYEXPIRED'
KEY_REVOKED       = b'KEYREVOKED'
NO_RECIPIENTS     = b'NO_RECP'
INVALID_RECIPIENT = b'INV_RECP'
KEY_CONSIDERED    = b'KEY_CONSIDERED'
NOAVAIL           = b'n/a'

# INV_RECP reason code descriptions.
INVALID_RECIPIENT_CAUSES = [
    'No specific reason given',
    'Not Found',
    'Ambiguous specification',
    'Wrong key usage',
    'Key revoked',
    'Key expired',
    'No CRL known',
    'CRL too old',
    'Policy mismatch',
    'Not a secret key',
    'Key not trusted',
    'Missing certificate',
    'Missing issuer certificate',
    'Key disabled',
    'Syntax error in specification'
    ]


def parse_status(status_buffer: str) -> dict:
    """Parse --status-fd output and return important information."""
    return parse_status_lines(status_buffer.splitlines())


def parse_status_lines(lines: list) -> dict:
    """Parse --status-fd output and return important information."""
    result = {'issue': NOAVAIL, 'recipient': NOAVAIL, 'cause': 'Unknown', 'key': NOAVAIL}

    LOG.debug('Processing stderr lines %s', lines)

    for line in lines:
        LOG.debug('At gnupg stderr line %s', line)
        if not line.startswith(STATUS_FD_PREFIX):
            continue

        if line.startswith(KEY_EXPIRED, STATUS_FD_PREFIX_LEN):
            result['issue'] = KEY_EXPIRED
        elif line.startswith(KEY_REVOKED, STATUS_FD_PREFIX_LEN):
            result['issue'] = KEY_REVOKED
        elif line.startswith(NO_RECIPIENTS, STATUS_FD_PREFIX_LEN):
            result['issue'] = NO_RECIPIENTS
        elif line.startswith(KEY_CONSIDERED, STATUS_FD_PREFIX_LEN):
            result['key'] = line.split(b' ')[2]
        elif line.startswith(INVALID_RECIPIENT, STATUS_FD_PREFIX_LEN):
            words = line.split(b' ')
            reason_code = int(words[2])
            result['recipient'] = words[3]
            result['cause'] = INVALID_RECIPIENT_CAUSES[reason_code]

    return result
