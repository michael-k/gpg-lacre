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

"""S/MIME handling module."""

import os

from M2Crypto import BIO, SMIME, X509

import logging
import lacre.text as text
import lacre.config as conf
import lacre.transport as xport

LOG = logging.getLogger(__name__)


#
# WARNING: This file is not covered with E2E tests.
#

def encrypt(raw_message, recipients, from_addr):
    """Encrypt with S/MIME."""
    if not conf.config_item_set('smime', 'cert_path'):
        LOG.info("No valid path for S/MIME certs found in config file. S/MIME encryption aborted.")
        return recipients

    cert_path = conf.get_item('smime', 'cert_path')+"/"
    s = SMIME.SMIME()
    sk = X509.X509_Stack()
    smime_to = list()
    cleartext_to = list()

    for addr in recipients:
        cert_and_email = _get_cert_for_email(addr, cert_path)

        if not (cert_and_email is None):
            (to_cert, normal_email) = cert_and_email
            LOG.debug("Found cert " + to_cert + " for " + addr + ": " + normal_email)
            smime_to.append(addr)
            x509 = X509.load_cert(to_cert, format=X509.FORMAT_PEM)
            sk.push(x509)
        else:
            cleartext_to.append(addr)

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
            out.write('X-Lacre: Encrypted by Lacre' + text.EOL_S)

        s.write(out, p7)

        LOG.debug(f"Sending message from {from_addr} to {smime_to}")

        send_msg = xport.SendFrom(from_addr)
        send_msg(out.read(), smime_to)

    if cleartext_to:
        LOG.debug(f"Unable to find valid S/MIME certificates for {cleartext_to}")

    return cleartext_to


def _path_comparator(insensitive: bool):
    if insensitive:
        return lambda filename, recipient: filename.casefold() == recipient
    else:
        return lambda filename, recipient: filename == recipient


def _get_cert_for_email(to_addr, cert_path):
    insensitive = conf.config_item_equals('default', 'mail_case_insensitive', 'yes')
    paths_equal = _path_comparator(insensitive)

    LOG.info('Retrieving certificate for %s from %s, insensitive=%s',
             to_addr, cert_path, insensitive)

    files_in_directory = os.listdir(cert_path)
    for filename in files_in_directory:
        file_path = os.path.join(cert_path, filename)
        if not os.path.isfile(file_path):
            continue

        if paths_equal(file_path, to_addr):
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
