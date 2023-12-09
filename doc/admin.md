# Lacre administration

## Command-line tool

There's a little tool for administrators.  As long as Lacre Python packages
are available via `PYTHONPATH`, you can use it like this:

```sh
python -m lacre.admin -h
```

Of course `-h` displays some help.

## Inspecting key confirmation queue

To find out how many keys are waiting to be confirmed, run:

```sh
python -m lacre.admin queue
```

## Inspecting identities registered

To list all identities, run:

```sh
python -m lacre.admin identities -a
```

To preview a particular identity, run:

```sh
python -m lacre.admin identities -e alice@example.com
```

## Importing identities from existing GnuPG keyring

If you already have a GnuPG keyring with your users' public keys or for some
reason Lacre's identity database needs to be re-populated with identities,
there's a command to do that:

```sh
python -m lacre.admin import -d /path/to/gnupg/directory
```

If you want to just re-populate the database, Lacre can remove all identities
prior to importing keys -- just add `-r` flag.
