"""Key management utilities."""

from datetime import datetime, timedelta

from lacre.config import get_item


def calculate_expiry_date(now: datetime) -> datetime:
    """Calculate date-time of key queue item expiry.

    Given current timestamp and configuration item
    [database]max_queue_hours, return a date-time object that should be
    older than any key in our confirmation queue.  If a key is older
    than this threshold, we should remove it."""
    max_hours = get_item('database', 'max_queue_hours', 1)
    return now - timedelta(hours=max_hours)
