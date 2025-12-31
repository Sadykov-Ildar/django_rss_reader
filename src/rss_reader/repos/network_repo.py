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
from rss_reader.rss.dtos import RssUrlArgs, RequestResult
from rss_reader.rss.rss_parser import RssParsedData
from rss_reader.repos.request_history import save_request


class NetworkRepo:
    def __init__(self, parser):
        self.parser = parser

    def get_parsed_results(
        self, rss_urls_args: Iterable[RssUrlArgs]
    ) -> list[tuple[RequestResult, RssParsedData]]:
        return asyncio.run(self._fetch_and_parse_rss_urls(rss_urls_args))

    def send_requests(self, rss_urls_args: Iterable[RssUrlArgs]) -> list[RequestResult]:
        return asyncio.run(self._send_requests(rss_urls_args))

    async def _fetch_and_parse_rss_urls(
        self,
        rss_urls_args: Iterable[RssUrlArgs],
    ) -> list[tuple[RequestResult, RssParsedData]]:
        requests_results = await self._send_requests(rss_urls_args)

        result = self.parser.parse(requests_results)

        return result

    async def _send_requests(
        self, rss_urls_args: Iterable[RssUrlArgs]
    ) -> list[RequestResult]:
        async with ClientSession(timeout=ClientTimeout(10)) as session:
            return await asyncio.gather(
                *(
                    self._async_request_for_rss(rss_urls_arg, session)
                    for rss_urls_arg in rss_urls_args
                )
            )

    @staticmethod
    async def _async_request_for_rss(
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
