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

import os
import subprocess

import configparser
import logging

import unittest


RELAY_SCRIPT = "test/utils/relay.py"
CONFIG_FILE = "test/gpg-mailgate.conf"


def _build_config(config):
    cp = configparser.RawConfigParser()

    cp.add_section("logging")
    cp.set("logging", "config", config["log_config"])

    cp.add_section("gpg")
    cp.set("gpg", "keyhome", config["gpg_keyhome"])

    cp.add_section('database')
    cp.set('database', 'enabled', 'yes')
    cp.set('database', 'url', 'sqlite:///test/lacre.db')
    cp.set('database', 'pooling_mode', 'optimistic')

    cp.add_section("smime")
    cp.set("smime", "cert_path", config["smime_certpath"])

    cp.add_section("relay")
    cp.set("relay", "host", "localhost")
    cp.set("relay", "port", config["port"])

    cp.add_section("daemon")
    cp.set("daemon", "host", "localhost")
    cp.set("daemon", "port", "10025")

    cp.add_section("enc_keymap")
    cp.set("enc_keymap", "alice@disposlab", "1CD245308F0963D038E88357973CF4D9387C44D7")
    cp.set("enc_keymap", "bob@disposlab", "19CF4B47ECC9C47AFA84D4BD96F39FDA0E31BB67")
    cp.set("enc_keymap", "evan@disposlab", "530B1BB2D0CC7971648198BBA4774E507D3AF5BC")

    cp.add_section("pgp_style")
    # Default style is PGP/Inline, so to cover more branches, one test identity
    # uses PGP/MIME.
    cp.set("pgp_style", "evan@disposlab", "mime")

    return cp


def _write_test_config(outfile, **config):
    logging.debug(f"Generating configuration with {config!r}")

    out = open(outfile, "w+")
    cp = _build_config(config)
    cp.write(out)
    out.close()

    logging.debug(f"Wrote configuration to {outfile}")


def _load_file(name):
    f = open(name, 'rb')
    contents = f.read()
    f.close()

    return contents


def _load_test_config():
    cp = configparser.ConfigParser()
    cp.read("test/e2e.ini")

    return cp


class SimpleMailFilterE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._e2e_config = _load_test_config()
        cls._e2e_config_path = os.path.join(os.getcwd(), CONFIG_FILE)

        # This environment variable is set in Makefile.
        cls._python_path = os.getenv('PYTHON', 'python3')

        _write_test_config(cls._e2e_config_path,
                           port				= cls._e2e_config.get("relay", "port"),
                           gpg_keyhome		= cls._e2e_config.get("dirs", "keys"),
                           smime_certpath	= cls._e2e_config.get("dirs", "certs"),
                           log_config		= cls._e2e_config.get("tests", "log_config"))

    def case_names(self):
        def is_test_case(case_name: str) -> bool:
            return case_name.startswith('case-')

        for tc in filter(is_test_case, self._e2e_config.sections()):
            yield tc

    def test_all_cases(self):
        for case_name in self.case_names():
            with self.subTest(case=case_name):
                self._execute_e2e_test(case_name)

    def _execute_e2e_test(self, case_name):
        """Read test case configuration from config and run that test case.

        Parameter case_name should refer to a section in test
        config file.  Each of these sections should contain
        following properties: 'descr', 'to', 'in' and 'out'.
        """
        gpglacre_cmd = self._python_command(
            'gpg-mailgate.py',
            self._e2e_config.get(case_name, 'to'))

        relay_cmd = self._python_command(
            self._e2e_config.get("relay", "script"),
            self._e2e_config.get("relay", "port"))

        logging.debug(f"Spawning relay: {relay_cmd}")
        relay_proc = subprocess.Popen(relay_cmd,
            stdin=None,
            stdout=subprocess.PIPE)

        logging.debug(f"Spawning GPG-Lacre: {gpglacre_cmd}, stdin = {self._e2e_config.get(case_name, 'in')}")

        # pass PATH because otherwise it would be dropped
        gpglacre_proc = subprocess.run(gpglacre_cmd,
            input=_load_file(self._e2e_config.get(case_name, "in")),
            capture_output=True,
            env={"GPG_MAILGATE_CONFIG": self._e2e_config_path,
                "PATH": os.getenv("PATH")})

        # Let the relay process the data.
        relay_proc.wait()

        (testout, _) = relay_proc.communicate()
        testout = testout.decode('utf-8')

        logging.debug(f"Read {len(testout)} characters of test output: '{testout}'")

        if 'out' in self._e2e_config[case_name]:
            expected = "\r\n" + self._e2e_config.get(case_name, "out")
            self.assertIn(expected, testout, self._e2e_config.get(case_name, "in"))
        else:
            unexpected = "\r\n" + self._e2e_config.get(case_name, "out-not")
            self.assertNotIn(unexpected, testout, self._e2e_config.get(case_name, "in"))

    def _python_command(self, script, *args):
        command = [self._python_path, script]
        command.extend(args)
        return command


if __name__ == '__main__':
    config = _load_test_config()

    logging.basicConfig(filename	= config.get("tests", "e2e_log"),
                        # Get raw values of log and date formats because they
                        # contain %-sequences and we don't want them to be
                        # expanded by the ConfigParser.
                        format		= config.get("tests", "e2e_log_format", raw=True),
                        datefmt		= config.get("tests", "e2e_log_datefmt", raw=True),
                        level		= logging.DEBUG)

    unittest.main()
