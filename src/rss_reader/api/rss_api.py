from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup
from django.utils import timezone

from aiohttp import (
    ClientSession,
    ClientTimeout,
    ClientResponseError,
    ClientConnectorError,
    ClientResponse,
)
from django.db import transaction

from rss_reader.api._refresh_intervals import (
    increase_update_interval,
    get_update_delay_in_hours,
    should_slow_down,
    decrease_update_interval,
    HOURS_IN_YEAR,
)
from rss_reader.api.entry_api import _create_entries
from rss_reader.api.feed_api import (
    create_feed_and_entries,
    create_user_feed,
    get_user_feeds,
)
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, RequestHistory
from vendoring import fastfeedparser


@dataclass
class RssUrlArgs:
    url: str
    etag: str = None
    modified: str = None
    delay: int = 0  # to avoid hammering the same server


@dataclass
class RequestResult:
    url: str
    status: int = 0
    headers: dict = ""
    response: Optional[ClientResponse] = None
    content: str = ""
    error_message: str = ""


def import_from_rss_urls(user, rss_urls: list[str]) -> str:
    error_messages = []

    rss_urls_args = []
    for rss_url in rss_urls:
        try:
            created = check_and_create_user_feed(rss_url, user)
            if not created:
                rss_urls_args.append(RssUrlArgs(url=rss_url))
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")

    parsed_results = asyncio.run(fetch_and_parse_rss_urls(rss_urls_args))

    for request_result, parsed_data, _ in parsed_results:
        error_message = request_result.error_message
        url = request_result.url
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        else:
            try:
                with transaction.atomic():
                    create_feed_and_entries(user, url, parsed_data)
            except URLValidationError as e:
                error_messages.append(f"{url}: {e.message}")

    error_message = "<br>".join(error_messages)

    return error_message


def check_and_create_user_feed(rss_url: str, user) -> bool:
    _validate_rss_url(user, rss_url)
    try:
        feed = Feed.objects.get(rss_url=rss_url)
    except Feed.DoesNotExist:
        created = False
    else:
        create_user_feed(feed, user)
        created = True

    return created


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

    if get_user_feeds(user).filter(feed__rss_url=rss_url).exists():
        raise URLValidationError("Feed with this url already exists.")


async def fetch_and_parse_rss_urls(
    rss_urls_args: Iterable[RssUrlArgs],
) -> list[tuple[RequestResult, dict, bool]]:
    requests_results = await send_request(rss_urls_args)

    result = parse_rss_responses(requests_results)

    return result


def parse_rss_responses(
    requests_results: list[RequestResult],
) -> list[tuple[RequestResult, dict, bool]]:
    result = []

    for request_result in requests_results:
        feed_has_entries = False
        parsed_data = {}
        if not request_result.error_message:
            if request_result.status != 304:
                parsed_data = fastfeedparser.parse(request_result.content)
                feed_has_entries = True

            resp_headers = request_result.headers
            parsed_data["etag"] = resp_headers.get("Etag") or ""
            parsed_data["modified"] = resp_headers.get("Last-modified") or ""

        result.append((request_result, parsed_data, feed_has_entries))

    return result


async def send_request(rss_urls_args: Iterable[RssUrlArgs]) -> list[RequestResult]:
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
    )

    req_headers = {
        "Accept-Encoding": "gzip, deflate",
        "User-Agent": "Django RSS Reader",
    }
    if rss_urls_arg.etag:
        req_headers["If-None-Match"] = rss_urls_arg.etag
    if rss_urls_arg.modified:
        req_headers["If-Modified-Since"] = rss_urls_arg.modified

    if rss_urls_arg.delay:
        await asyncio.sleep(rss_urls_arg.delay)
    try:
        async with session.get(rss_urls_arg.url, headers=req_headers) as response:
            resp_headers = response.headers

            result.status = response.status
            result.headers = resp_headers
            result.response = response
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


def refresh_feed(
    feed: Feed, parsed_data: dict, feed_has_entries, request_result: RequestResult
):
    # TODO: rss has different tags for hints as to when is a bad time to poll for updates
    feed.etag = parsed_data.get("etag", "") or ""
    feed.modified = parsed_data.get("modified", "") or ""

    current_time = timezone.now()
    status = request_result.status

    feed.last_updated = current_time
    feed.last_exception = request_result.error_message

    feed.last_response_body = None
    if status not in {200, 304}:
        # response body could have hint that we need to show to user
        feed.last_response_body = request_result.content

    old_entry_count = feed.entry_count

    if feed_has_entries:
        UserFeed.objects.filter(feed=feed).update(stale=True)
        _create_entries(feed, parsed_data)
    # we need to check this now, because response could just have stale entries
    # or entries that we filtered out
    new_entries = feed.entry_count > old_entry_count

    if status in {301, 308}:
        # moved permanently
        new_location = request_result.headers.get("Location")
        if new_location:
            feed.last_exception = f"Moved from {feed.rss_url} to {new_location}"
            feed.rss_url = new_location
    elif status in {302, 307}:
        new_location = request_result.headers.get("Location")
        if new_location:
            # moved temporarily
            feed.last_exception = (
                f"Temporarily moved from {feed.rss_url} to {new_location}"
            )
        pass
    elif status == 410:
        # gone
        feed.updates_enabled = False
        feed.disabled_reason = 'Server responded with [status 410] "gone"'

    update_interval = feed.update_interval
    update_delay = get_update_delay_in_hours(request_result.headers)
    if update_delay:
        update_interval = update_delay
    else:
        if should_slow_down(status, new_entries, request_result.error_message):
            # slow down
            update_interval = increase_update_interval(update_interval)
        else:
            # new updates - speed up a little bit
            update_interval = decrease_update_interval(update_interval)

    if update_interval > HOURS_IN_YEAR:
        feed.updates_enabled = False
        feed.disabled_reason = "Last updated more than a year ago"
    if update_interval < 2:
        update_interval = 2

    feed.update_interval = update_interval
    feed.update_after = current_time + timedelta(hours=update_interval)
    feed.save()


def process_rss_url(request, rss_url):
    rss_url = rss_url.strip()
    user = request.user

    try:
        created = check_and_create_user_feed(rss_url, user)
    except URLValidationError as e:
        return e.message
    if created:
        # Done without errors
        return ""

    requests_results = asyncio.run(send_request([RssUrlArgs(url=rss_url)]))
    request_result = requests_results[0]
    error_message = request_result.error_message
    if error_message:
        return error_message

    soup = BeautifulSoup(request_result.content, "lxml")
    is_html = False
    if is_soup_html(soup):
        # HTML - need to get feed urls from contents
        rss_urls = extract_feed_urls_from_html(rss_url, soup)
        if rss_urls:
            error_message = import_from_rss_urls(user, rss_urls)
            is_html = True

    if not is_html:
        parsed_results = parse_rss_responses(requests_results)
        request_result, parsed_data, _ = parsed_results[0]
        error_message = request_result.error_message
        if error_message:
            return error_message
        try:
            with transaction.atomic():
                create_feed_and_entries(user, request_result.url, parsed_data)
        except URLValidationError as e:
            return e.message

    return error_message


def is_soup_html(soup: BeautifulSoup) -> bool:
    if len(soup.find_all()) > 2:  # More than just <html> and <body>
        return True
    # look for specific common HTML tags
    common_tags = ["div", "p", "a", "img", "span", "table", "h1", "head", "body"]
    for tag in common_tags:
        if soup.find(tag):
            return True
    return bool(soup.find())


def extract_feed_urls_from_html(rss_url, soup: BeautifulSoup):
    rss_urls = set()
    for link in soup.find_all(
        "link", rel="alternate", type=("application/rss+xml", "application/atom+xml")
    ):
        href = link.get("href")
        if href:
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(rss_url, href)
            rss_urls.add(href)

    for link in soup.find_all("link", rel="feed"):
        href = link.get("href")
        if href:
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(rss_url, href)
            rss_urls.add(href)

    rss_urls = list(rss_urls)
    return rss_urls
