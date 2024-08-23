#
# lacre
#
# This file is part of the lacre source code.
#
# lacre is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# lacre source code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with lacre source code. If not, see <http://www.gnu.org/licenses/>.
#

import configparser
import logging
import subprocess
import os
import time
import unittest
from typing import Dict


def _spawn(cmd, *, env_add: Dict = None):
    env_dict = {
        "PATH": os.getenv("PATH"),
        "PYTHONPATH": os.getcwd(),
        "LANG": 'en_US.UTF-8',
        "LACRE_CONFIG": "test/lacre-daemon.conf"
        }
    if env_add:
        env_dict.update(env_add)

    logging.debug(f"Spawning command: {cmd} with environment: {env_dict!r}")
    return subprocess.Popen(cmd,
                            stdin=None,
                            stdout=subprocess.PIPE,
                            env=env_dict)


def _interrupt(proc):
    proc.terminate()


def _send(host, port, mail_from, mail_to, message):
    logging.debug(f"Sending message to {host}:{port}")
    python = os.getenv("PYTHON") or "python"
    p = _spawn([python,
        "test/utils/sendmail.py",
        "-f", mail_from,
        "-t", mail_to,
        "-m", message])

    # Perform subprocess's internal resource management:
    p.communicate()


def _load_test_config():
    cp = configparser.ConfigParser()
    cp.read("test/e2e.ini")
    return cp


class AdvancedMailFilterE2ETest(unittest.TestCase):
    """End-to-end tests for Advanced Mail Filter.

    These tests are described by e2e.ini file, each case being a
    separate section.  All cases are executed following the same
    procedure:
    1. start up a mail relay mock;
    2. load test message;
    3. send the message to the daemon;
    4. check if message received by relay mock meets criteria.

    Before any case is executed, the daemon is started and finally it's
    terminated by sending it a SIGINT signal."""

    @classmethod
    def setUpClass(cls):
        """Start up the daemon."""
        cls.config = _load_test_config()

        python = os.getenv("PYTHON", "python")

        logging.info('Starting the server...')
        cls.server = _spawn([python, '-m', 'lacre.daemon'], env_add={'SQLALCHEMY_WARN_20': '1'})

    @classmethod
    def tearDownClass(cls):
        """Terminate the daemon."""
        logging.info('Closing the server (SIGINT): %s', (cls.server))
        _interrupt(cls.server)

    def case_names(self):
        """A generator yielding a sequence of test case names."""
        def is_test_case(case_name: str) -> bool:
            return case_name.startswith('case-')

        for tc in filter(is_test_case, self.config.sections()):
            yield tc

    def test_all_cases(self):
        for case_name in self.case_names():
            with self.subTest(case=case_name):
                self._execute_case(self.config, case_name=case_name)

    def _execute_case(self, config, case_name):
        logging.info(f"Executing case {case_name}")
        python = os.getenv("PYTHON", "python")

        relay_mock = _spawn([python, "test/utils/relay.py", "2500"])
        time.sleep(1)                            # Wait for the relay to start up.

        _send("localhost", 10025, "dave@disposlab",
              config.get(case_name, 'to'), config.get(case_name, 'in'))

        (test_out, _) = relay_mock.communicate()

        test_out = test_out.decode('utf-8')
        logging.debug(f"Read {len(test_out)} characters of output: '{test_out}'")

        if 'out' in config[case_name]:
            expected = '\r\n' + self.config.get(case_name, 'out')
            self.assertIn(expected, test_out, self.config.get(case_name, 'in'))
        else:
            unexpected = '\r\n' + self.config.get(case_name, 'out-not')
            self.assertNotIn(unexpected, test_out, self.config.get(case_name, 'in'))


if __name__ == '__main__':
    logging.basicConfig(filename="test/logs/daemon-test.log",
                        format="%(asctime)s %(pathname)s:%(lineno)d %(levelname)s [%(funcName)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",
                        level=logging.DEBUG)

    unittest.main()
