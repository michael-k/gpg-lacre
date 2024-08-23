.POSIX:
.PHONY: test e2etest unittest crontest daemontest pre-clean clean restore-keyhome
.SUFFIXES: .gv .png

#
# On systems where Python 3.x binary has a different name, just
# overwrite the name/path on the command line, like:
#
#     make test PYTHON=/usr/local/bin/python3.8
#
# This macro is passed via environment to test/e2e_test.py, where it's
# used to compute further commands.
#
PYTHON = python

GRAPHVIZ = dot

#
# SQLite database used during tests
#
# This database stores key queue and identity repository for e2etest,
# daemontest, and crontest.
#
TEST_DB = test/lacre.db

#
# List of graph files
#
GRAPHS = doc/key-lifecycle.png

#
# Main goal to run all tests.
#
test: e2etest daemontest unittest crontest

#
# Build graphviz diagrams.
#
doc: ${GRAPHS}

#
# Run a set of end-to-end tests.
#
# Test scenarios are described and configured by the test/e2e.ini file.
# Basically this is just a script that feeds Lacre with known input and checks
# whether output meets expectations.
#
e2etest: test/tmp test/logs pre-clean restore-keyhome
	$(PYTHON) test/e2e_test.py

#
# Run a basic cron-job test.
#
# We use PYTHONPATH to make sure that cron.py can import GnuPG
# package.  We also set LACRE_CONFIG env. variable to make sure
# it slurps the right config.
#
crontest: clean-db $(TEST_DB)
	LACRE_CONFIG=test/lacre-daemon.conf PYTHONPATH=`pwd`	\
	$(PYTHON) webgate-cron.py

$(TEST_DB):
	$(PYTHON) test/utils/schema.py $(TEST_DB)

#
# Run an e2e test of Advanced Content Filter.
#
daemontest: restore-keyhome
	$(PYTHON) test/daemon_test.py

# Before running the crontest goal we need to make sure that the
# database gets regenerated.
clean-db:
	rm -f $(TEST_DB)

#
# Run unit tests
#
unittest:
	LACRE_CONFIG=test/lacre.conf $(PYTHON) -m unittest discover -s test/modules

pre-clean:
	rm -fv test/lacre.conf
	rm -f test/logs/*.log

restore-keyhome:
	git restore test/keyhome
	git restore test/keyhome.other

test/tmp:
	mkdir test/tmp

test/logs:
	mkdir test/logs

clean: pre-clean clean-db
	rm -rfv test/tmp test/logs

# Convert dot source to PNG image.
.gv.png:
	$(GRAPHVIZ) -Tpng $< > ${<:S/.gv/.png/}
