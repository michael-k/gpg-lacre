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
