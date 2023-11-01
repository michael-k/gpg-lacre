#!/usr/bin/python

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

import sqlalchemy
import smtplib
import markdown
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import logging
import lacre
import lacre.config as conf
import lacre.dbschema as db
from lacre.repositories import KeyConfirmationQueue, IdentityRepository
from lacre.notify import notify

# Read configuration from /etc/gpg-mailgate.conf
conf.load_config()

lacre.init_logging(conf.get_item('logging', 'config'))
LOG = logging.getLogger('webgate_cron.py')

import GnuPG


def _setup_db_connection(url):
    engine = sqlalchemy.create_engine(url)
    LOG.debug('Initialised database engine: %s', engine)
    return (engine, engine.connect())


def _define_db_schema():
    return (db.GPGMW_KEYS, db.GPGMW_IDENTITIES)


def _validate_config():
    missing = conf.validate_config(additional=conf.CRON_REQUIRED)
    if missing:
        LOG.error('Missing config parameters: %s', missing)


_validate_config()

if conf.flag_enabled('database', 'enabled') and conf.config_item_set('database', 'url'):
    (engine, conn) = _setup_db_connection(conf.get_item("database", "url"))
    (gpgmw_keys, gpgmw_identities) = _define_db_schema()

    identities = IdentityRepository(gpgmw_identities, conn)
    key_queue = KeyConfirmationQueue(gpgmw_keys, conn)

    key_dir = conf.get_item('gpg', 'keyhome')
    LOG.debug('Using GnuPG with home directory in %s', key_dir)

    result_set = key_queue.fetch_keys()

    for armored_key, row_id, email in result_set:
        # delete any other public keys associated with this confirmed email address
        key_queue.delete_keys(row_id, email)
        GnuPG.delete_key(key_dir, email)
        LOG.info('Deleted key for <%s> via import request', email)

        if armored_key.strip():  # we have this so that user can submit blank key to remove any encryption
            if GnuPG.confirm_key(armored_key, email):
                # import the key to gpg
                (fingerprint, _) = GnuPG.add_key(key_dir, armored_key)

                key_queue.mark_accepted(row_id)
                identities.register(email, fingerprint)

                LOG.info('Imported key from <%s>', email)
                if conf.flag_enabled('cron', 'send_email'):
                    notify("PGP key registration successful", "registrationSuccess.md", email)
            else:
                key_queue.delete_keys(row_id)
                LOG.warning('Import confirmation failed for <%s>', email)

                if conf.flag_enabled('cron', 'send_email'):
                    notify("PGP key registration failed", "registrationError.md", email)
        else:
            # delete key so we don't continue processing it
            key_queue.delete_keys(row_id)
            if conf.flag_enabled('cron', 'send_email'):
                notify("PGP key deleted", "keyDeleted.md", email)

    stat2_result_set = key_queue.fetch_keys_to_delete()
    for email, row_id in stat2_result_set:
        GnuPG.delete_key(key_dir, email)
        key_queue.delete_keys(row_id)
        LOG.info('Deleted key for <%s>', email)
else:
    print("Warning: doing nothing since database settings are not configured!")
    LOG.error("Warning: doing nothing since database settings are not configured!")
