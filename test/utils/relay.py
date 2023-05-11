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
EXIT_NETWORK = 2
EXIT_UNKNOWN = 3

ENCODING = 'utf-8'

BUFFER_SIZE = 4096
EOM = b"\r\n.\r\n"
LAST_LINE = -3


def _welcome(msg):
    return b"220 %b\r\n" % (msg)


def _ok(msg=b"OK"):
    return b"250 %b\r\n" % (msg)


def _bye():
    return b"251 Bye"


def _provide_message():
    return b"354 Enter a message, ending it with a '.' on a line by itself\r\n"


def _receive_and_confirm(session):
    session.recv(BUFFER_SIZE)
    session.sendall(_ok())


def _receive_and_ignore(session):
    session.recv(BUFFER_SIZE)


def _localhost_at(port):
    return ('127.0.0.1', port)


def _receive_bytes(conn) -> bytes:
    return conn.recv(BUFFER_SIZE)


def _listen(port, sock):
    try:
        sock.bind(_localhost_at(port))
        sock.listen(1)
    except socket.error as e:
        print("Cannot connect", e)
        logging.exception('Cannot connect')
        sys.exit(EXIT_NETWORK)


def _serve(port) -> bytes:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _listen(port, s)

    logging.debug("About to accept a connection...")
    (conn, addr) = s.accept()
    logging.debug(f"Accepting connection from {conn}")
    conn.sendall(_welcome(b"TEST SERVER"))

    _receive_and_confirm(conn)                       # Ignore HELO/EHLO
    _receive_and_confirm(conn)                       # Ignore sender address
    _receive_and_confirm(conn)                       # Ignore recipient address

    _receive_and_ignore(conn)
    conn.sendall(_provide_message())

    # Consume until we get <CR><LF>.<CR><LF>, the end-of-message marker.
    message = b''
    while not message.endswith(EOM):
        buf = _receive_bytes(conn)
        logging.debug('Received data: %s', buf)
        message += buf
    conn.sendall(_ok(b"OK, id=test"))

    conn.recv(BUFFER_SIZE)
    conn.sendall(_bye())

    conn.close()

    logging.debug('Received %d bytes of data', len(message))

    # Trim EOM marker as we're only interested in the message body.
    return message[:-len(EOM)]


def _error(msg, exit_code):
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
    _error("Usage: relay.py PORT_NUMBER", EXIT_UNAVAILABLE)

port = int(sys.argv[1])

try:
    body = _serve(port)
    logging.debug('Parsing message')
    msg = email.message_from_bytes(body, policy=email.policy.SMTP)
    print(msg)
except ConnectionResetError:
    logging.exception('Communication issue')
    _error('Could not receive complete message', EXIT_NETWORK)
except BrokenPipeError:
    logging.exception('Pipe error')
    _error('Pipe error', EXIT_UNKNOWN)
