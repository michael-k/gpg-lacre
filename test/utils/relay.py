#!/usr/local/bin/python2
#
# This quick-and-dirty script supports only the happy case of SMTP session,
# i.e. what gpg-mailgate/gpg-lacre needs to deliver encrypted email.
#
# It listens on the port given as the only command-line argument and consumes a
# message, then prints it to standard output.  The goal is to be able to
# compare that output with expected clear-text or encrypted message body.
#

import sys
import socket

import logging
import email
import email.policy


EXIT_UNAVAILABLE = 1

ENCODING = 'utf-8'

BUFFER_SIZE = 4096
EOM = b"\r\n.\r\n"
LAST_LINE = -3


def welcome(msg):
    return b"220 %b\r\n" % (msg)

def ok(msg = b"OK"):
    return b"250 %b\r\n" % (msg)

def bye():
    return b"251 Bye"

def provide_message():
    return b"354 Enter a message, ending it with a '.' on a line by itself\r\n"

def receive_and_confirm(session):
    session.recv(BUFFER_SIZE)
    session.sendall(ok())

def localhost_at(port):
    return ('127.0.0.1', port)

def serve(port) -> bytes:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(localhost_at(port))
        logging.info(f"Listening on localhost, port {port}")
        s.listen(1)
        logging.info("Listening...")
    except socket.error as e:
        print("Cannot connect", e)
        logging.error(f"Cannot connect {e}")
        sys.exit(EXIT_UNAVAILABLE)

    logging.debug("About to accept a connection...")
    (conn, addr) = s.accept()
    logging.debug(f"Accepting connection from {conn}")
    conn.sendall(welcome(b"TEST SERVER"))

    receive_and_confirm(conn)                       # Ignore HELO/EHLO
    receive_and_confirm(conn)                       # Ignore sender address
    receive_and_confirm(conn)                       # Ignore recipient address

    b = conn.recv(BUFFER_SIZE)
    logging.debug('Got data: %s', repr(b))
    conn.sendall(provide_message())

    # Consume until we get <CR><LF>.<CR><LF>, the end-of-message marker.
    message = b''
    while not message.endswith(EOM):
        message += conn.recv(BUFFER_SIZE)
    conn.sendall(ok(b"OK, id=test"))

    conn.recv(BUFFER_SIZE)
    conn.sendall(bye())

    conn.close()

    logging.debug(f"Received {len(message)} bytes of data")

    # Trim EOM marker as we're only interested in the message body.
    return message[:-len(EOM)]

def error(msg, exit_code):
    logging.error(msg)
    print("ERROR: %s" % (msg))
    sys.exit(exit_code)


# filename is relative to where we run the tests from, i.e. the project root
# directory
logging.basicConfig(filename='test/logs/relay.log',
                    format='%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)

if len(sys.argv) < 2:
    error("Usage: relay.py PORT_NUMBER", EXIT_UNAVAILABLE)

port = int(sys.argv[1])
body = serve(port)

msg = email.message_from_bytes(body, policy=email.policy.SMTP)
print(msg)
