# Advanced Filter

## Postfix Filters

There are two types of Postfix mail filters: Simple Filters and Advanced
Filters. Simple Filters are executed for each incoming email as a new
process, which may turn out to be expensive in terms of resources. Advanced
Filters work as a mail-processing proxies.

For detailed documentation, see [FILTER README](https://www.postfix.org/FILTER_README.html).

## Installation

Just use the following command to install dependencies:

```
pip install -r requirements.txt
```

## Configuration

Lacre Advanced Filter, also known as daemon, is configured in the `[daemon]`
section of configuration file. Two obligatory parameters to be defined there
are:

  * `host` -- IP address or a host name;
  * `port` -- TCP port Lacre should listen on.

The other very important section is `[relay]`, which by default uses Simple
Filter destination. It has to be adjusted for Advanced Filter to work,
setting port to `10026`.

Command to spawn a Lacre daemon process is:

```
LACRE_CONFIG=/etc/lacre.conf PYTHONPATH=... python -m lacre.daemon
```

Two environment variables used here are:

  * `LACRE_CONFIG` (not mandatory) -- path to Lacre configuration,
    unless it's kept in default location (`/etc/lacre.conf`).
  * `PYTHONPATH` (not mandatory) -- location of Lacre modules. You can place
    them below your Python's `site-packages` to be reachable by any other
    Python software.
