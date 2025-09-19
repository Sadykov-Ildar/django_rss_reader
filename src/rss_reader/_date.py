import calendar
from datetime import datetime, timezone


def _get_datetime(date_str) -> datetime | None:
    if date_str:
        return datetime.fromtimestamp(calendar.timegm(date_str), timezone.utc)
    return None
