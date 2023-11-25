# Testing

First tests have been set up to cover GPG Mailgate with at least basic test
that would be easy to run. The tests are called "end-to-end", meaning that we
feed some input to GPG Mailgate and inspect the output.

## Running tests

To run tests, use command `make test`.

There are 4 types of tests:

  * `make e2etest` -- they cover a complete Lacre flow, from feeding it with
    an email to accepting its encrypted form;
  * `make daemontest` -- similar to the original `e2etest` goal, but tests the
    behaviour of the Lacre Daemon, i.e. key part of the Advanced Content
    Filter.
  * `make unittest` -- just small tests of small units of code;
  * `make crontest` -- execute cron job with a SQLite database.

E2E tests (`make e2etest`) should produce some helpful logs, so inspect
contents of `test/logs` directory if something goes wrong.

If your system's Python binary isn't found in your `$PATH` or you want to use
a specific binary, use make's macro overriding: `make test
PYTHON=/path/to/python`.

## Key building blocks

- *Test Script* (`test/e2e_test.py`) and *Daemon Test Script*
  (`test/daemon_test.py`) that orchestrate the other components. They perform
  test cases described in the *Test Configuration*. They spawn *Test Mail
  Relay* and *GPG Mailgate* in appropriate order.
- *Test Mail Relay* (`test/relay.py`), a simplistic mail daemon that only
  supports the happy path. It accepts a mail message and prints it to
  stdandard output.
- *Test Configuration* (`test/e2e.ini`) specifies test cases: their input,
  expected results and helpful documentation. It also specifies the port that
  the *Test Mail Relay* should listen on.

## Limitations

Currently tests only check if the message has been encrypted, without
verifying that the correct key has been used. That's because we don't know
(yet) how to have a reproducible encrypted message. Option
`--faked-system-time` wasn't enough to produce identical output.

## Troubleshooting

When things go wrong, be sure to study `test/logs/e2e.log` and
`test/logs/gpg-mailgate.log` files -- they contain some useful information.

## Test identities

There are several identities in test/keyhome and in the test database:

* alice@disposlab: 1CD245308F0963D038E88357973CF4D9387C44D7
* bob@disposlab: 19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67
* evan@disposlab: 530B1BB2D0CC7971648198BBA4774E507D3AF5BC
