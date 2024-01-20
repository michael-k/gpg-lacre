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

    result_set = key_queue.fetch_keys()

    for armored_key, row_id, email in result_set:
        # delete any other public keys associated with this confirmed email address
        key_queue.delete_keys(row_id, email=email)
        identities.delete(email)
        GnuPG.delete_key(key_dir, email)
        LOG.info('Deleted key for <%s> via import request', email)

        if armored_key.strip():  # we have this so that user can submit blank key to remove any encryption
            if GnuPG.confirm_key(armored_key, email):
                # import the key to gpg
                (fingerprint, _) = GnuPG.add_key(key_dir, armored_key)

                key_queue.mark_accepted(row_id)
                identities.register_or_update(email, fingerprint)

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
            LOG.debug('Empty key received, just deleting')

            key_queue.delete_keys(row_id)
            if conf.flag_enabled('cron', 'send_email'):
                notify("PGP key deleted", "keyDeleted.md", email)

    LOG.info('Cleaning up after a round of key confirmation')
    for email, row_id in key_queue.fetch_keys_to_delete():
        LOG.debug('Removing key from keyring: %s', email)
        GnuPG.delete_key(key_dir, email)

        LOG.debug('Removing key from identity store: %s', row_id)
        key_queue.delete_keys(row_id)

        LOG.info('Deleted key for <%s>', email)
except:
    LOG.exception('Unexpected issue during key confirmation')
