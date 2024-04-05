#!/usr/bin/python

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

import sys
from datetime import datetime
import logging
import lacre
import lacre.config as conf
from lacre.notify import notify

# Read configuration from /etc/lacre.conf
conf.load_config()

lacre.init_logging(conf.get_item('logging', 'config'))
LOG = logging.getLogger('webgate-cron.py')

import GnuPG
from lacre.repositories import KeyConfirmationQueue, IdentityRepository, init_engine


def _validate_config():
    missing = conf.validate_config(additional=conf.CRON_REQUIRED)
    if missing:
        LOG.error('Missing config parameters: %s', missing)
        exit(lacre.EX_CONFIG)


def import_key(key_dir, armored_key, key_id, email, key_queue, identities):
    # import the key to gpg
    (fingerprint, _) = GnuPG.add_key(key_dir, armored_key)

    key_queue.mark_accepted(key_id)
    identities.register_or_update(email, fingerprint)

    LOG.info('Imported key from: %s', email)
    if conf.flag_enabled('cron', 'send_email'):
        notify("PGP key registration successful", "registrationSuccess.md", email)


def import_failed(key_id, email, key_queue):
    key_queue.delete_keys(key_id)
    LOG.warning('Key confirmation failed: %s', email)

    if conf.flag_enabled('cron', 'send_email'):
        notify("PGP key registration failed", "registrationError.md", email)


def delete_key(key_id, email, key_queue):
    # delete key so we don't continue processing it
    LOG.debug('Empty key received, deleting known key from: %s', email)

    key_queue.delete_keys(key_id, email)
    if conf.flag_enabled('cron', 'send_email'):
        notify("PGP key deleted", "keyDeleted.md", email)


def cleanup(key_dir, key_queue):
    """Delete keys and queue entries."""
    LOG.debug('Removing no longer needed keys from queue')
    for email, row_id in key_queue.fetch_keys_to_delete():
        LOG.debug('Removing key from keyring: %s', email)
        GnuPG.delete_key(key_dir, email)

        LOG.debug('Removing key from identity store: %s', row_id)
        key_queue.delete_keys(row_id)

        LOG.info('Deleted key for: %s', email)

    now = datetime.now()
    key_queue.delete_expired_queue_items(now)


_validate_config()

if not (conf.flag_enabled('database', 'enabled') and conf.config_item_set('database', 'url')):
    print("Warning: doing nothing since database settings are not configured!")
    LOG.error("Warning: doing nothing since database settings are not configured!")
    sys.exit(lacre.EX_CONFIG)


try:
    db_engine = init_engine(conf.get_item('database', 'url'))

    identities = IdentityRepository(engine=db_engine)
    key_queue = KeyConfirmationQueue(engine=db_engine)

    key_dir = conf.get_item('gpg', 'keyhome')
    LOG.debug('Using GnuPG with home directory in %s', key_dir)

    for armored_key, row_id, email in key_queue.fetch_keys():
        # delete any other public keys associated with this confirmed email address
        key_queue.delete_keys(row_id, email=email)
        identities.delete(email)
        GnuPG.delete_key(key_dir, email)
        LOG.info('Deleted key via import request for: %s', email)

        if not armored_key.strip():  # we have this so that user can submit blank key to remove any encryption
            # delete key so we don't continue processing it
            delete_key(row_id, email, key_queue)
            continue

        if GnuPG.confirm_key(armored_key, email):
            import_key(key_dir, armored_key, row_id, email, key_queue, identities)
        else:
            import_failed(row_id, email, key_queue)

    cleanup(key_dir, key_queue)
except:
    LOG.exception('Unexpected issue during key confirmation')
