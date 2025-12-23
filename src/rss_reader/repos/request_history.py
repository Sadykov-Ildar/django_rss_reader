from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from rss_reader.models import RequestHistory

if TYPE_CHECKING:
    from rss_reader.use_cases.rss.dtos import RequestResult


async def save_request(request_result: RequestResult):
    header_string = ""
    for key, value in request_result.headers.items():
        header_string += f"{key}: {value}\n"

    await RequestHistory.objects.acreate(
        url=request_result.url,
        status=request_result.status,
        headers=header_string,
        content=request_result.content,
    )


def delete_request_history_older_than(two_weeks_ago: datetime):
    RequestHistory.objects.filter(created_at__lt=two_weeks_ago).delete()
