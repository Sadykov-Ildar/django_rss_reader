from datetime import datetime, timedelta

from django.utils import timezone


def get_datetime(date_str) -> datetime | None:
    if date_str:
        return datetime.fromisoformat(date_str)
    return None


def timedelta_in_human(delta: timedelta) -> str:
    delta = abs(delta)  # there are issues if delta is negative
    seconds = delta.seconds
    days = delta.days

    hours = (seconds // 3600) % 24
    minutes = (seconds // 60) % 60
    seconds = seconds % 60

    result = " ".join(
        filter(
            None,
            (
                f"{days} days" if days else "",
                f"{hours} hours" if hours else "",
                f"{minutes} minutes" if minutes else "",
                f"{seconds} seconds" if seconds else "",
            ),
        )
    )

    return result


def get_delta_from_current_time_in_human(date_time: datetime) -> str:
    current_time = timezone.now()
    delta = current_time - date_time
    result_str = timedelta_in_human(delta)

    in_future = date_time > current_time
    if in_future:
        result_str = "in " + result_str
    else:
        result_str = result_str + " ago"

    return result_str
