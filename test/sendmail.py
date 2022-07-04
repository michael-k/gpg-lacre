import smtplib


def _send(host, port, from_addr, recipients, message):
    smtp = smtplib.SMTP(host, port)
    # smtp.starttls()
    # try:
    # breakpoint()
    smtp.sendmail(from_addr, recipients, message)
    # except smtplib.SMTPDataError as e:
    #     print(f"Couldn't deliver message.\nGot error: {e}\n")


message = """\
From: dave@disposlab
To: alice@disposlab
Subject: Test message

Lorem ipsum dolor sit amet.
"""

_send('localhost', 10025, 'dave@disposlab', ['alice@disposlab'], message)
