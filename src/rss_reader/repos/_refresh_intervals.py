import re
from datetime import datetime
from typing import TYPE_CHECKING

from django.utils import timezone

from rss_reader.constants import (
    HOURS_IN_DAY,
    HOURS_IN_THREE_DAYS,
    HOURS_IN_WEEK,
    HOURS_IN_MONTH,
    HOURS_IN_YEAR,
)

if TYPE_CHECKING:
    from rss_reader.rss.dtos import RequestResult

max_age_regex = re.compile(r"max-age=(\d+)", re.IGNORECASE)


def get_update_interval_in_hours(
    update_interval: int, new_entries: bool, request_result: RequestResult
) -> int:
    update_delay = __get_update_delay_in_hours(request_result.headers)
    if update_delay:
        update_interval = update_delay
    else:
        if __should_slow_down(
            request_result.status, new_entries, request_result.error_message
        ):
            # slow down
            update_interval = __increase_update_interval(update_interval)
        else:
            # new updates - speed up a little bit
            update_interval = __decrease_update_interval(update_interval)

    if update_interval < 2:
        update_interval = 2

    return update_interval


def __increase_update_interval(update_interval: int):
    if 0 <= update_interval <= HOURS_IN_DAY:
        update_interval += 2
    elif HOURS_IN_DAY < update_interval <= HOURS_IN_THREE_DAYS:
        update_interval += 6
    elif HOURS_IN_THREE_DAYS < update_interval <= HOURS_IN_WEEK:
        update_interval += HOURS_IN_DAY
    elif HOURS_IN_WEEK < update_interval <= HOURS_IN_MONTH:
        update_interval += HOURS_IN_THREE_DAYS
    elif HOURS_IN_MONTH < update_interval:
        update_interval = HOURS_IN_MONTH

    return update_interval


def __decrease_update_interval(update_interval: int):
    if 0 <= update_interval <= HOURS_IN_DAY:
        update_interval -= 1
    elif HOURS_IN_DAY < update_interval <= HOURS_IN_THREE_DAYS:
        update_interval -= 3
    elif HOURS_IN_THREE_DAYS < update_interval <= HOURS_IN_WEEK:
        update_interval -= HOURS_IN_DAY
    elif HOURS_IN_WEEK < update_interval <= HOURS_IN_MONTH:
        update_interval -= HOURS_IN_THREE_DAYS
    elif HOURS_IN_MONTH < update_interval <= HOURS_IN_YEAR:
        # Between month and a year - update once a month
        update_interval = HOURS_IN_MONTH

    return update_interval


def __get_update_delay_in_hours(headers: dict) -> int:
    """
    Returns the amount of seconds of delay before making another request to the server
    """
    delay = __get_retry_after(headers)

    if not delay:
        delay = __get_max_age(headers)

    return int(delay / 3600)


def __get_retry_after(headers: dict) -> int:
    retry_after = 0
    header_value = headers.get("Retry-after", "")
    if header_value:
        try:
            # Attempt to parse as seconds
            retry_after = int(header_value)
        except ValueError:
            try:
                # Attempt to parse as HTTP-date (RFC 1123)
                retry_time = datetime.strptime(
                    header_value, "%a, %d %b %Y %H:%M:%S GMT"
                )
                time_difference = retry_time - timezone.now()
                retry_after = max(0, int(time_difference.total_seconds()))
            except ValueError:
                retry_after = 0

    return retry_after


def __get_max_age(headers: dict):
    """
    Returns max-age from headers in seconds
    """
    cache_control = headers.get("Cache-Control")
    if cache_control:
        match = max_age_regex.search(cache_control)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass

    return 0


def __should_slow_down(status, new_entries, error_message):
    if not new_entries or error_message:
        return True
    # Slow down on certain specific statuses
    if status in {
        304,
        403,
        404,
        429,
    }:
        return True

    # Slow down on 4xx or 5xx statuses
    str_status = str(status)
    if len(str_status) == 3 and str_status[0] in {4, 5}:
        return True

    return False
