import smtplib
import sys
import getopt


def _send(host, port, from_addr, recipients, message):
    smtp = smtplib.SMTP(host, port)
    # smtp.starttls()
    # try:
    # breakpoint()
    smtp.sendmail(from_addr, recipients, message)
    # except smtplib.SMTPDataError as e:
    #     print(f"Couldn't deliver message.\nGot error: {e}\n")


sender = recipient = message = None

for opt, value in getopt.getopt(sys.argv[1:], "f:t:m:"):
    if opt == "f":
        sender = value
    if opt == "t":
        recipient = value
    if opt == "m":
        message = value

if message is None:
    message = """\
From: dave@disposlab
To: alice@disposlab
Subject: Test message

Lorem ipsum dolor sit amet.
"""

_send('localhost', 10025, sender, [recipient], message)
