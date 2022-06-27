.POSIX:
.PHONY: test e2etest unittest crontest pre-clean clean restore-keyhome

#
# On systems where Python 3.x binary has a different name, just
# overwrite the name/path on the command line, like:
#
#     make test PYTHON=/usr/local/bin/python3.8
#
# This marco is passed via environment to test/e2e_test.py, where it's
# used to compute further commands.
#
PYTHON = python3

TEST_DB = test/lacre.db

#
# Main goal to run tests.
#
test: e2etest unittest crontest

#
# Run a set of end-to-end tests.
#
# Test scenarios are described and configured by the test/e2e.ini
# file.  Basically this is just a script that feeds GPG Mailgate with
# known input and checks whether output meets expectations.
#
e2etest: test/tmp test/logs pre-clean restore-keyhome
	$(PYTHON) test/e2e_test.py

#
# Run a basic cron-job test.
#
# We use PYTHONPATH to make sure that cron.py can import GnuPG
# package.  We also set GPG_MAILGATE_CONFIG env. variable to make sure
# it slurps the right config.
#
crontest: clean-db $(TEST_DB)
	GPG_MAILGATE_CONFIG=test/gpg-mailgate-cron-test.conf PYTHONPATH=`pwd` $(PYTHON) gpg-mailgate-web/cron.py

$(TEST_DB):
	$(PYTHON) test/schema.py $(TEST_DB)

# Before running the crontest goal we need to make sure that the
# database gets regenerated.
clean-db:
	rm -f $(TEST_DB)

#
# Run unit tests
#
unittest:
	$(PYTHON) -m unittest discover -s test

pre-clean:
	rm -fv test/gpg-mailgate.conf
	rm -f test/logs/*.log

restore-keyhome:
	git restore test/keyhome

test/tmp:
	mkdir test/tmp

test/logs:
	mkdir test/logs

clean: pre-clean
	rm -rfv test/tmp test/logs
