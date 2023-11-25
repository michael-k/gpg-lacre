"""Lacre administrative tool.

This is a command-line tool expected to be run by a person who knows what they
are doing.  Also, please read the docs first.
"""

import sys
import argparse
import logging

import lacre
import lacre.config as conf

conf.load_config()
lacre.init_logging(conf.get_item('logging', 'config'))

import lacre.repositories as repo
import lacre.dbschema as db

LOG = logging.getLogger('lacre.admin')


def sub_queue(args):
    """Sub-command to inspect queue contents."""
    LOG.debug('Inspecting queue...')

    conn = repo.connect(conf.get_item('database', 'url'))
    queue = repo.KeyConfirmationQueue(conn)

    cnt = queue.count_keys()

    print(f'Keys in the queue: {cnt}')


def main():
    conf.validate_config(additional=conf.SCRIPT_REQUIRED)

    parser = argparse.ArgumentParser(
        prog='lacre.admin',
        description='Lacre Admin\'s best friend'
        )

    sub_commands = parser.add_subparsers(help='Sub-commands', required=True)

    # cmd_import = sub_commands.add_parser('import',
    #     help='Load identities from GnuPG directory to Lacre database'
    #     )
    # cmd_import.add_argument('-d', '--homedir', help='Specify GnuPG directory')
    # cmd_import.set_defaults(operation=sub_import)

    cmd_queue = sub_commands.add_parser('queue',
        help='Inspect key queue',
        aliases=['q']
        )
    cmd_queue.set_defaults(operation=sub_queue)

    # cmd_identities = sub_commands.add_parser('identities',
    #     help='Inspect identity database',
    #     aliases=['id']
    #     )
    # cmd_identities.add_argument('-e', '--email', help='Check single email')
    # cmd_identities.add_argument('-a', '--all', help='List all emails', action='store_true')
    # cmd_identities.set_defaults(operation=sub_identities)

    user_request = parser.parse_args()
    user_request.operation(user_request)


if __name__ == '__main__':
    main()
