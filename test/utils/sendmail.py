import logging
import smtplib
import sys
import getopt
from email import message_from_binary_file
from email.policy import SMTPUTF8


def _load_file(name) -> bytes:
    with open(name, 'rb') as f:
        return f.read()


def _load_message(name):
    with open(name, 'rb') as f:
        return message_from_binary_file(f, policy=SMTPUTF8)


def _send_message(host, port, from_addr, recipients, message):
    logging.info(f"From {from_addr} to {recipients} at {host}:{port}")
    try:
        smtp = smtplib.SMTP(host, port)
        return smtp.sendmail(from_addr, recipients, message.as_bytes())
    except smtplib.SMTPDataError as e:
        logging.error(f"Couldn't deliver message. Got error: {e}")
        return None
    except ConnectionRefusedError as e:
        logging.exception(f"Connection refused: {e}")
        return None
    except:
        logging.exception('Unexpected exception was thrown')
        return None


# The poinf of this function is to do _almost_ what SMTP.sendmail does, but
# without enforcing ASCII.  We want to test Lacre with not necessarily valid
# messages.
def _send_bytes(host: str, port, from_addr: str, recipients, message: bytes):
    try:
        smtp = smtplib.SMTP(host, port)
        smtp.ehlo_or_helo_if_needed()
        smtp.mail(from_addr)
        for r in recipients:
            smtp.rcpt(r)
        smtp.data(message)
    except:
        logging.exception('Unexpected exception was thrown')


logging.basicConfig(filename="test/logs/sendmail.log",
                    format="%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.DEBUG)

sender = recipient = message = None

opts, _ = getopt.getopt(sys.argv[1:], "f:t:m:")
for opt, value in opts:
    if opt == "-f":
        sender = value
        logging.debug(f"Sender is {sender!r}")
    if opt == "-t":
        recipient = value
        logging.debug(f"Recipient is {recipient!r}")
    if opt == "-m":
        message = _load_file(value)
        logging.debug(f"Message is {message}")

if message is None or sender is None or recipient is None:
    print('Use options to provide: -f sender -t recipient -m message')

_send_bytes('localhost', 10025, sender, [recipient], message)
