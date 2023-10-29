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
from sqlalchemy.sql import select, delete, and_
import smtplib
import markdown
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import logging
import lacre
import lacre.config as conf

# Read configuration from /etc/gpg-mailgate.conf
conf.load_config()

lacre.init_logging(conf.get_item('logging', 'config'))
LOG = logging.getLogger('webgate-cron.py')

import GnuPG

def _load_file(name):
    f = open(name)
    data = f.read()
    f.close()
    return data


def _authenticate_maybe(smtp):
    if conf.config_item_equals('smtp', 'enabled', 'true'):
        LOG.debug(f"Connecting to {conf.get_item('smtp', 'host')}:{conf.get_item('smtp', 'port')}")
        smtp.connect(conf.get_item('smtp', 'host'), conf.get_item('smtp', 'port'))
        smtp.ehlo()
        if conf.config_item_equals('smtp', 'starttls', 'true'):
            LOG.debug("StartTLS enabled")
            smtp.starttls()
        smtp.ehlo()
        smtp.login(conf.get_item('smtp', 'username'), conf.get_item('smtp', 'password'))


def _send_msg(mailsubject, messagefile, recipients = None):
    mailbody = _load_file(conf.get_item('cron', 'mail_templates') + "/" + messagefile)
    msg = MIMEMultipart("alternative")

    msg["From"] = conf.get_item('cron', 'notification_email')
    msg["To"] = recipients
    msg["Subject"] = mailsubject

    msg.attach(MIMEText(mailbody, 'plain'))
    msg.attach(MIMEText(markdown.markdown(mailbody), 'html'))

    if conf.config_item_set('relay', 'host') and conf.config_item_set('relay', 'enc_port'):
        relay = (conf.get_item('relay', 'host'), int(conf.get_item('relay', 'enc_port')))
        smtp = smtplib.SMTP(relay[0], relay[1])
        _authenticate_maybe(smtp)
        smtp.sendmail(conf.get_item('cron', 'notification_email'), recipients, msg.as_string())
    else:
        LOG.info("Could not send mail due to wrong configuration")


def _setup_db_connection(url):
    engine = sqlalchemy.create_engine(url)
    return (engine, engine.connect())


def _define_db_schema():
    meta = sqlalchemy.MetaData()

    gpgmw_keys = sqlalchemy.Table('gpgmw_keys', meta,
                                  sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
                                  sqlalchemy.Column('email', sqlalchemy.String(256)),
                                  sqlalchemy.Column('publickey', sqlalchemy.Text),
                                  sqlalchemy.Column('confirm', sqlalchemy.String(32)),
                                  sqlalchemy.Column('status', sqlalchemy.Integer),
                                  sqlalchemy.Column('time', sqlalchemy.DateTime))

    identities = sqlalchemy.Table('gpgmw_identities', meta,
        sqlalchemy.Column('email', sqlalchemy.String(256), index=True),
        sqlalchemy.Column('key_id', sqlalchemy.String(64), index=True))

    return (gpgmw_keys, identities)


if conf.config_item_equals('database', 'enabled', 'yes') and conf.config_item_set('database', 'url'):
    (engine, conn) = _setup_db_connection(conf.get_item("database", "url"))
    (gpgmw_keys, gpgmw_identities) = _define_db_schema()

    selq = select(gpgmw_keys.c.publickey, gpgmw_keys.c.id, gpgmw_keys.c.email)\
        .where(and_(gpgmw_keys.c.status == 0, gpgmw_keys.c.confirm == ""))\
        .limit(100)
    LOG.debug(f"Retrieving keys to be processed: {selq}")
    result_set = conn.execute(selq)

    for armored_key, row_id, email in result_set:
        # delete any other public keys associated with this confirmed email address
        delq = delete(gpgmw_keys).where(and_(gpgmw_keys.c.email == email, gpgmw_keys.c.id != row_id))
        LOG.debug(f"Deleting public keys associated with confirmed email: {delq}")
        conn.execute(delq)
        GnuPG.delete_key(conf.get_item('gpg', 'keyhome'), email)
        LOG.info('Deleted key for <%s> via import request', email)

        if armored_key.strip():  # we have this so that user can submit blank key to remove any encryption
            if GnuPG.confirm_key(armored_key, email):
                # import the key to gpg
                GnuPG.add_key(conf.get_item('gpg', 'keyhome'), armored_key)

                # mark key as accepted
                modq = gpgmw_keys.update().where(gpgmw_keys.c.id == row_id).values(status=1)
                LOG.debug("Key imported, updating key: %s", modq)
                conn.execute(modq)

                # add to identity database
                update_identity = gpgmw_identities.insert().values(email=email, key_id=armored_key)
                conn.execute(update_identity)

                LOG.warning('Imported key from <%s>', email)
                if conf.config_item_equals('cron', 'send_email', 'yes'):
                    _send_msg("PGP key registration successful", "registrationSuccess.md", email)
            else:
                delq = delete(gpgmw_keys).where(gpgmw_keys.c.id == row_id)
                LOG.debug(f"Cannot confirm key, deleting it: {delq}")
                conn.execute(delq)              # delete key
                LOG.warning('Import confirmation failed for <' + email + '>')
                if conf.config_item_equals('cron', 'send_email', 'yes'):
                    _send_msg("PGP key registration failed", "registrationError.md", email)
        else:
            # delete key so we don't continue processing it
            delq = delete(gpgmw_keys).where(gpgmw_keys.c.id == row_id)
            LOG.debug(f"Deleting key: {delq}")
            conn.execute(delq)
            if conf.config_item_equals('cron', 'send_email', 'yes'):
                _send_msg("PGP key deleted", "keyDeleted.md", email)

    # delete keys
    stat2q = select(gpgmw_keys.c.email, gpgmw_keys.c.id).where(gpgmw_keys.c.status == 2).limit(100)
    stat2_result_set = conn.execute(stat2q)

    for email, row_id in stat2_result_set:
        GnuPG.delete_key(conf.get_item('gpg', 'keyhome'), email)
        delq = delete(gpgmw_keys).where(gpgmw_keys.c.id == row_id)
        LOG.debug(f"Deleting keys that have already been processed: {delq}")
        conn.execute(delq)
        LOG.info('Deleted key for <' + email + '>')
else:
    print("Warning: doing nothing since database settings are not configured!")
    LOG.error("Warning: doing nothing since database settings are not configured!")
