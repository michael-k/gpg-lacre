#
# gpg-mailgate
#
# This file is part of the gpg-mailgate source code.
#
# gpg-mailgate is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gpg-mailgate source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gpg-mailgate source code. If not, see <http://www.gnu.org/licenses/>.
#

import configparser
import logging
import subprocess
import os
import time


def _spawn(cmd):
    env_dict = {
        "PATH": os.getenv("PATH"),
        "PYTHONPATH": os.getcwd(),
        "GPG_MAILGATE_CONFIG": "test/gpg-mailgate-daemon-test.conf"
        }
    logging.debug(f"Spawning command: {cmd} with environment: {env_dict!r}")
    return subprocess.Popen(cmd,
                            stdin=None,
                            stdout=subprocess.PIPE,
                            env=env_dict)


def _interrupt(proc):
    # proc.send_signal(signal.SIGINT)
    proc.terminate()


def _load(name):
    logging.debug(f"Loading file {name}")
    f = open(name, "r")
    contents = f.read()
    f.close()
    return contents


def _send(host, port, mail_from, mail_to, message):
    logging.debug(f"Sending message to {host}:{port}")
    _spawn([os.getenv("PYTHON") or "python",
            "test/utils/sendmail.py",
            "-f", mail_from,
            "-t", mail_to,
            "-m", message])


def _load_test_config():
    cp = configparser.ConfigParser()
    cp.read("test/e2e.ini")
    return cp


def _report_result(message_file, expected, test_output):
    status = None
    if expected in test_output:
        status = "Success"
    else:
        status = "Failure"

    print(message_file.ljust(30), status)


def _execute_case(config, case_name):
    logging.info(f"Executing case {case_name}")
    python = os.getenv("PYTHON", "python")

    relay_mock = _spawn([python, "test/utils/relay.py", "2500"])
    time.sleep(1)                            # Wait for the relay to start up.

    _send("localhost", 10025, "dave@disposlab",
          config.get(case_name, 'to'), config.get(case_name, 'in'))

    relay_mock.wait()
    (test_out, _) = relay_mock.communicate()

    test_out = test_out.decode('utf-8')
    logging.debug(f"Read {len(test_out)} characters of output: '{test_out}'")

    _report_result(config.get(case_name, "in"), config.get(case_name, "out"), test_out)


def _main():
    conf = _load_test_config()

    logging.basicConfig(filename="test/logs/daemon-test.log",
                        format="%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.DEBUG)

    logging.info("Starting Lacre Daemon tests...")
    python = os.getenv("PYTHON", "python")

    server = _spawn([python, "-m", "lacre.daemon"])

    for case_no in range(1, conf.getint("tests", "cases")):
        _execute_case(conf, case_name=f"case-{case_no}")

    _interrupt(server)


if __name__ == '__main__':
    _main()
