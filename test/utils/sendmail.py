import logging
import smtplib
import sys
import getopt


def _load_file(name):
    f = open(name, 'r')
    contents = f.read()
    f.close()
    return contents


def _send(host, port, from_addr, recipients, message):
    logging.info(f"From {from_addr} to {recipients} at {host}:{port}")
    try:
        smtp = smtplib.SMTP(host, port)
        # smtp.starttls()
        return smtp.sendmail(from_addr, recipients, message)
    except smtplib.SMTPDataError as e:
        logging.error(f"Couldn't deliver message. Got error: {e}")
        return None
    except ConnectionRefusedError as e:
        logging.exception(f"Connection refused: {e}")
        return None


logging.basicConfig(filename="test/logs/sendmail.log",
                    format="%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    level=logging.DEBUG)

sender = recipient = message = None

opts, _ = getopt.getopt(sys.argv[1:], "f:t:m:")
for opt, value in opts:
    if opt == "-f":
        sender = value
        logging.debug(f"Sender is {sender}")
    if opt == "-t":
        recipient = value
        logging.debug(f"Recipient is {recipient}")
    if opt == "-m":
        message = _load_file(value)
        logging.debug(f"Message is {message}")

if message is None:
    message = """\
From: dave@disposlab
To: alice@disposlab
Subject: Test message

Lorem ipsum dolor sit amet.
"""

_send('localhost', 10025, sender, [recipient], message)
