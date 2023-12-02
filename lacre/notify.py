"""Lacre notification sender"""

import logging
import lacre
import lacre.config as conf

# Read configuration from /etc/gpg-mailgate.conf
conf.load_config()

LOG = logging.getLogger(__name__)


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


def notify(mailsubject, messagefile, recipients = None):
    """Send notification email."""

    mailbody = _load_file(conf.get_item('cron', 'mail_templates') + "/" + messagefile)
    msg = MIMEMultipart("alternative")

    msg["From"] = conf.get_item('cron', 'notification_email')
    msg["To"] = recipients
    msg["Subject"] = mailsubject

    msg.attach(MIMEText(mailbody, 'plain'))
    msg.attach(MIMEText(markdown.markdown(mailbody), 'html'))

    if conf.config_item_set('relay', 'host') and conf.config_item_set('relay', 'enc_port'):
        (host, port) = conf.relay_params()
        smtp = smtplib.SMTP(host, port)
        _authenticate_maybe(smtp)
        smtp.sendmail(conf.get_item('cron', 'notification_email'), recipients, msg.as_string())
    else:
        LOG.info("Could not send mail due to wrong configuration")
