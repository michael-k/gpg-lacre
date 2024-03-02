import unittest

from logging import getLogger, ERROR, Handler
from lacre.stats import time_logger

def make_exception_raiser(logger):
    def f():
        with time_logger('Just a test', logger):
            logger.info('Doing something')
            raise Exception('this is a test')
    return f


class LogRecordCollector(Handler):
    logged_records = []

    def handle(self, r):
        self.logged_records.append(self.format(r))


class ExecutionTimeLoggerTest(unittest.TestCase):
    def test_exception_handling(self):
        handler = LogRecordCollector()
        logger = getLogger('test-logger')
        logger.addHandler(handler)

        f = make_exception_raiser(logger)

        self.assertRaises(Exception, f)
        self.assertLogs(logger, ERROR)
        self.assertEqual(len(handler.logged_records), 3)
        self.assertEqual(handler.logged_records[0], 'Start: Just a test')
        self.assertEqual(handler.logged_records[1], 'Doing something')

        # Exception record should include the timing result and the traceback...
        self.assertRegex(handler.logged_records[2], '^Just a test took 0 ms, raised exception\nTraceback.*')
        # ...as well as the original exception
        self.assertRegex(handler.logged_records[2], 'Exception: this is a test$')
