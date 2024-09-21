"""Key management utilities."""

from datetime import datetime, timedelta
import logging

from lacre.config import get_item


# By default, we let keys stay in confirmation queue for 1 hour.
_DEFAULT_TTL = 1


LOG = logging.getLogger(__name__)


def calculate_expiry_date(now: datetime) -> datetime:
    """Calculate date-time of key queue item expiry.

    Given current timestamp and configuration item
    [database]max_queue_hours, return a date-time object that should be
    older than any key in our confirmation queue.  If a key is older
    than this threshold, we should remove it."""
    max_hours = _get_ttl()
    return now - timedelta(hours=max_hours)


def _get_ttl():
    max_hours = get_item('database', 'max_queue_hours', _DEFAULT_TTL)
    try:
        ttl =  int(max_hours)
        LOG.debug('Key configmration queue max item age: %d hours', ttl)
        return ttl
    except ValueError:
        # Not a valid integer, so we return the default.
        LOG.exception('Invalid max_queue_hours format: %s, using default (%d)', max_hours, _DEFAULT_TTL)
        return _DEFAULT_TTL
