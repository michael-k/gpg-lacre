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


LINE_FINGERPRINT = 'fpr'
LINE_USER_ID = 'uid'

POS_FINGERPRINT = 9

LOG = logging.getLogger(__name__)


def _build_command(key_home, *args, **kwargs):
    cmd = ["gpg", '--homedir', key_home] + list(args)
    return cmd


def public_keys(keyhome):
    """List public keys from keyring KEYHOME."""
    cmd = _build_command(keyhome, '--list-keys', '--with-colons')
    p = subprocess.Popen(cmd, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()

    keys = dict()
    fingerprint = None
    email = None
    for line in p.stdout.readlines():
        line = line.decode(sys.getdefaultencoding())
        if line[0:3] == LINE_FINGERPRINT:
            fingerprint = line.split(':')[POS_FINGERPRINT]
        if line[0:3] == LINE_USER_ID:
            if ('<' not in line or '>' not in line):
                continue
            email = line.split('<')[1].split('>')[0]
        if not (fingerprint is None or email is None):
            keys[fingerprint] = email
            fingerprint = None
            email = None

    p.stdout.close()
    p.stderr.close()
    return keys


def _to_bytes(s) -> bytes:
    if isinstance(s, str):
        return bytes(s, sys.getdefaultencoding())
    else:
        return s


# Confirms a key has a given email address by importing it into a temporary
# keyring.  If this operation succeeds and produces a message mentioning the
# expected email, a key is confirmed.
def confirm_key(content, email):
    """Verify that the key CONTENT is assigned to identity EMAIL."""
    tmpkeyhome = ''
    content = _to_bytes(content)
    expected_email = _to_bytes(email.lower())

    while True:
        tmpkeyhome = '/tmp/' + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(12))
        if not os.path.exists(tmpkeyhome):
            break

    # let only the owner access the directory, otherwise gpg would complain
    os.mkdir(tmpkeyhome, mode=0o700)
    localized_env = os.environ.copy()
    localized_env["LANG"] = "C"
    p = subprocess.Popen(_build_command(tmpkeyhome, '--import', '--batch'), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=localized_env)
    result = p.communicate(input=content)[1]
    confirmed = False

    for line in result.split(b"\n"):
        if b'imported' in line and b'<' in line and b'>' in line:
            if line.split(b'<')[1].split(b'>')[0].lower() == expected_email:
                confirmed = True
                break
            else:
                break # confirmation failed

    # cleanup
    shutil.rmtree(tmpkeyhome)

    return confirmed


# adds a key and ensures it has the given email address
def add_key(keyhome, content):
    """Register new key CONTENT in the keyring KEYHOME."""
    if isinstance(content, str):
        content = bytes(content, sys.getdefaultencoding())
    p = subprocess.Popen(_build_command(keyhome, '--import', '--batch'), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.communicate(input=content)
    p.wait()


def delete_key(keyhome, email):
    """Remove key assigned to identity EMAIL from keyring KEYHOME."""
    from email.utils import parseaddr
    result = parseaddr(email)

    if result[1]:
        # delete all keys matching this email address
        p = subprocess.Popen(_build_command(keyhome, '--delete-key', '--batch', '--yes', result[1]), stdin=None, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        return True

    return False


class GPGEncryptor:
    """A wrapper for 'gpg -e' command."""

    def __init__(self, keyhome, recipients=None, charset=None):
        """Initialise the wrapper."""
        self._keyhome = keyhome
        self._message = b''
        self._recipients = list()
        self._charset = charset
        if recipients is not None:
            self._recipients.extend(recipients)

    def update(self, message):
        """Append MESSAGE to buffer about to be encrypted."""
        self._message += message

    def encrypt(self):
        """Feed GnuPG with the message."""
        p = subprocess.Popen(self._command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        encdata = p.communicate(input=self._message)[0]
        return (encdata, p.returncode)

    def _command(self):
        cmd = _build_command(self._keyhome, "--trust-model", "always", "--batch", "--yes", "--pgp7", "--no-secmem-warning", "-a", "-e")

        # add recipients
        for recipient in self._recipients:
            cmd.append("-r")
            cmd.append(recipient)

        # add on the charset, if set
        if self._charset:
            cmd.append("--comment")
            cmd.append('Charset: ' + self._charset)

        LOG.debug(f'Built command: {cmd!r}')
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
