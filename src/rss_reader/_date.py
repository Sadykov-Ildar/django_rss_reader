from datetime import datetime


def _get_datetime(date_str) -> datetime | None:
    if date_str:
        return datetime.fromisoformat(date_str)
    return None
