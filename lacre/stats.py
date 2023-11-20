"""Insights into Lacre's inner workings."""

import time
import logging

class ExecutionTimeLogger:
    """Context-manager that measures how much time some operation took and logs it."""

    def __init__(self, message: str, logger: logging.Logger):
        self._message = message
        self._log = logger
        self._start = None

    def __enter__(self):
        self._start = time.process_time()

    def __exit__(self, exc_type=None, exc_value=None, traceback=None):
        end = time.process_time()
        ellapsed = (end - self._start) * 1000

        if exc_type:
            self._log.error('%s took %d ms, raised exception %s', self._message, ellapsed, exc_type)
        else:
            self._log.info('%s took %d ms', self._message, ellapsed)

def time_logger(msg: str, logger: logging.Logger):
    return ExecutionTimeLogger(msg, logger)
