"""Lacre administrative tool.

This is a command-line tool expected to be run by a person who knows what they
are doing.  Also, please read the docs first.
"""

import sys
import argparse
import logging

import GnuPG
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


def sub_identities(args):
    """Sub-command to inspect identity database."""
    LOG.debug('Inspecting identities...')

    conn = repo.connect(conf.get_item('database', 'url'))
    identities = repo.IdentityRepository(conn)

    all_identities = identities.freeze_identities()
    if args.email:
        all_rev = all_identities.emails()
        print('-', args.email, all_rev[args.email])
    else:
        for id_ in all_identities:
            print('-', all_identities[id_], id_)


def sub_import(args):
    """Sub-command to import all identities known to GnuPG into Lacre database."""
    LOG.debug('Importing identities...')
    source_dir = args.homedir or conf.get_item('gpg', 'keyhome')

    public = GnuPG.public_keys(source_dir)

    conn = repo.connect(conf.get_item('database', 'url'))
    identities = repo.IdentityRepository(conn)

    total = 0
    for (fingerprint, email) in public.items():
        LOG.debug('Importing %s - %s', email, fingerprint)
        identities.register_or_update(email, fingerprint)
        total += 1

    LOG.debug('Imported %d identities', total)
    print(f'Imported {total} identities')


def main():
    conf.validate_config(additional=conf.SCRIPT_REQUIRED)

    general_conf = conf.config_source()
    log_conf = conf.get_item('logging', 'config')

    parser = argparse.ArgumentParser(
        prog='lacre.admin',
        description='Lacre Admin\'s best friend',
        epilog=f'Config read from {general_conf}. For diagnostic info, see {log_conf}'
        )

    sub_commands = parser.add_subparsers(help='Sub-commands', required=True)

    cmd_import = sub_commands.add_parser('import',
        help='Load identities from GnuPG directory to Lacre database'
        )
    cmd_import.add_argument('-d', '--homedir', help='specify GnuPG directory (default: use configured dir.)')
    cmd_import.set_defaults(operation=sub_import)

    cmd_queue = sub_commands.add_parser('queue',
        help='Inspect key queue',
        aliases=['q']
        )
    cmd_queue.set_defaults(operation=sub_queue)

    cmd_identities = sub_commands.add_parser('identities',
        help='Inspect identity database',
        aliases=['id']
        )
    cmd_identities.add_argument('-e', '--email', help='look up a single email')
    cmd_identities.set_defaults(operation=sub_identities)

    user_request = parser.parse_args()

    user_request.operation(user_request)


if __name__ == '__main__':
    main()
