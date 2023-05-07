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
import unittest


def _spawn(cmd):
    env_dict = {
        "PATH": os.getenv("PATH"),
        "PYTHONPATH": os.getcwd(),
        "LANG": 'en_US.UTF-8',
        "GPG_MAILGATE_CONFIG": "test/gpg-mailgate-daemon-test.conf"
        }
    logging.debug(f"Spawning command: {cmd} with environment: {env_dict!r}")
    return subprocess.Popen(cmd,
                            stdin=None,
                            stdout=subprocess.PIPE,
                            env=env_dict)


def _interrupt(proc):
    proc.terminate()


def _load(name):
    logging.debug(f"Loading file {name}")
    f = open(name, "r")
    contents = f.read()
    f.close()
    return contents


def _send(host, port, mail_from, mail_to, message):
    logging.debug(f"Sending message to {host}:{port}")
    p = _spawn([os.getenv("PYTHON") or "python",
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


def _identity(x):
    return x


def _inversion(x):
    return not(x)


def _report_result(message_file, expected, test_output, boolean_func=_identity):
    status = None
    expected_line = "\r\n" + expected  # + "\r\n"
    cond_met = boolean_func(expected_line in test_output)
    if cond_met:
        status = "Success"
    else:
        status = "Failure"

    print(message_file.ljust(84, '.'), status)


class AdvancedMailFilterE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = _load_test_config()

        python = os.getenv("PYTHON", "python")

        logging.info('Starting the server...')
        cls.server = _spawn([python, '-m', 'lacre.daemon'])

    @classmethod
    def tearDownClass(cls):
        logging.info('Closing the server (SIGINT): %s', (cls.server))
        _interrupt(cls.server)

    def case_names(self):
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
