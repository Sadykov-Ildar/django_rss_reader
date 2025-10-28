import asyncio
from dataclasses import dataclass
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from django.db import IntegrityError, transaction

from rss_reader.api.entry_api import _create_entries
from rss_reader.api.feed_api import create_feed_and_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, RequestHistory
from vendoring import fastfeedparser


@dataclass
class RssUrlArgs:
    url: str
    etag: str = None
    modified: str = None


def import_from_rss_urls(user, rss_urls: list[str]) -> str:
    error_messages = []

    rss_urls_args = []
    for rss_url in rss_urls:
        try:
            _validate_rss_url(user, rss_url)
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")
            continue
        try:
            feed = Feed.objects.get(rss_url=rss_url)
        except Feed.DoesNotExist:
            rss_urls_args.append(RssUrlArgs(url=rss_url))
        else:
            try:
                UserFeed.objects.create(user=user, feed=feed)
            except IntegrityError:
                error_messages.append(f"{rss_url}: Feed with this url already exists.")

    responses_by_rss_urls = asyncio.run(get_responses_by_rss_urls(rss_urls_args))

    for url, response, _, error_message in responses_by_rss_urls:
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        else:
            try:
                with transaction.atomic():
                    create_feed_and_entries(user, url, response)
            except URLValidationError as e:
                error_messages.append(f"{url}: {e.message}")

    error_message = "<br>".join(error_messages)

    return error_message


def _validate_rss_url(user, rss_url):
    # TODO: проверить на sql-иньекции, вставку путей к файлам, и всячески обезопасить
    if not rss_url:
        raise URLValidationError("Empty rss url")

    parsed_url = urlparse(rss_url)

    if not parsed_url.netloc:
        raise URLValidationError("Invalid URL")

    scheme = parsed_url.scheme
    if scheme not in ("http", "https"):
        raise URLValidationError("Url must start with http or https.")

    if UserFeed.objects.filter(user=user, feed__rss_url=rss_url).exists():
        raise URLValidationError("Feed with this url already exists.")


async def get_responses_by_rss_urls(
    rss_urls_args: Iterable[RssUrlArgs],
) -> list[tuple[str, dict, bool, str]]:
    async with ClientSession(timeout=ClientTimeout(30)) as session:
        return await asyncio.gather(
            *(
                _async_parse_feed(
                    rss_urls_arg,
                    session,
                )
                for rss_urls_arg in rss_urls_args
            )
        )


async def _async_parse_feed(
    rss_urls_arg: RssUrlArgs, session: ClientSession
) -> tuple[str, dict, bool, str]:
    new_entries_added = False
    error_message = ""
    response = {}

    req_headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:143.0) Gecko/20100101 Firefox/143.0",
    }
    if rss_urls_arg.etag:
        req_headers["If-None-Match"] = rss_urls_arg.etag
    if rss_urls_arg.modified:
        req_headers["If-Modified-Since"] = rss_urls_arg.modified

    try:
        async with session.get(rss_urls_arg.url, headers=req_headers) as response:
            response.raise_for_status()
            resp_headers = response.headers

            content = await response.text()

            await save_request(content, resp_headers, rss_urls_arg.url, response.status)

            if response.status == 304:
                response = {
                    "etag": resp_headers.get("Etag") or "",
                    "modified": resp_headers.get("Last-modified") or "",
                }
            else:
                response = fastfeedparser.parse(content)
                response["etag"] = resp_headers.get("etag") or ""
                response["modified"] = resp_headers.get("Last-modified") or ""

                new_entries_added = True

    except (ValueError, HTTPError) as e:
        error_message = "Some error occurred: " + str(e)
    except TimeoutError:
        error_message = "Time out"
    except (ClientResponseError, URLError) as e:
        error_message = "Error: " + str(e)

    return rss_urls_arg.url, response, new_entries_added, error_message


async def save_request(content: str, resp_headers, url: str, status:int):
    header_string = ""
    for key, value in resp_headers.items():
        header_string += f"{key}: {value}\n"

    await RequestHistory.objects.acreate(
        url=url,
        status=status,
        headers=header_string,
        content=content,
    )


def refresh_feed(feed: Feed, response, new_entries_added):
    feed.etag = response.get("etag", "") or ""
    feed.modified = response.get("modified", "") or ""
    feed.save()

    if new_entries_added:
        UserFeed.objects.filter(feed=feed).update(stale=True)
        _create_entries(feed, response)
