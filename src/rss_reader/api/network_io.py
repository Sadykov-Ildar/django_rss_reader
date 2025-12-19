from __future__ import annotations

import asyncio
from typing import Iterable
from urllib.error import HTTPError, URLError

from aiohttp import (
    ClientSession,
    ClientTimeout,
    ClientResponseError,
    ClientConnectorError,
)

from django_rss_reader.version import get_version
from rss_reader.api.dtos import RssUrlArgs, RequestResult
from rss_reader.api.rss_parser import parse_rss_responses, RssParsedData
from rss_reader.repos.request_history import save_request


async def fetch_and_parse_rss_urls(
    rss_urls_args: Iterable[RssUrlArgs],
) -> list[tuple[RequestResult, RssParsedData]]:
    requests_results = await send_requests(rss_urls_args)

    result = parse_rss_responses(requests_results)

    return result


async def send_requests(rss_urls_args: Iterable[RssUrlArgs]) -> list[RequestResult]:
    async with ClientSession(timeout=ClientTimeout(10)) as session:
        return await asyncio.gather(
            *(
                async_request_for_rss(rss_urls_arg, session)
                for rss_urls_arg in rss_urls_args
            )
        )


async def async_request_for_rss(
    rss_urls_arg: RssUrlArgs, session: ClientSession
) -> RequestResult:
    error_message = ""
    result = RequestResult(
        url=rss_urls_arg.url,
        headers={},
    )

    version = get_version()

    req_headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": f"Django RSS Reader/{version}",
    }
    if rss_urls_arg.etag:
        req_headers["If-None-Match"] = rss_urls_arg.etag
    if rss_urls_arg.modified:
        req_headers["If-Modified-Since"] = rss_urls_arg.modified

    if rss_urls_arg.delay:
        await asyncio.sleep(rss_urls_arg.delay * 2)
    try:
        async with session.get(rss_urls_arg.url, headers=req_headers) as response:
            resp_headers = response.headers

            result.status = response.status
            result.headers = resp_headers
            result.content = await response.text()

            await save_request(result)
            response.raise_for_status()

    except (ValueError, HTTPError) as e:
        error_message = "Some error occurred: " + str(e)
    except TimeoutError:
        error_message = "Time out"
    except (ClientResponseError, URLError) as e:
        error_message = "Error: " + str(e)
    except ClientConnectorError as e:
        error_message = "Couldn't connect: " + str(e)

    result.error_message = error_message

    return result
