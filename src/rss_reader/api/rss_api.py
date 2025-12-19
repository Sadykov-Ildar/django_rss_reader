from __future__ import annotations
import asyncio
from collections import Counter
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from django.utils import timezone

from django.db import transaction, IntegrityError

from rss_reader.api._refresh_intervals import (
    increase_update_interval,
    get_update_delay_in_hours,
    should_slow_down,
    decrease_update_interval,
)
from rss_reader.api.dtos import RssUrlArgs, RequestResult, RssParsedData
from rss_reader.api.network_io import (
    fetch_and_parse_rss_urls,
    parse_rss_responses,
    send_requests,
)
from rss_reader.constants import HOURS_IN_YEAR
from rss_reader.repos.feed_repo import (
    create_feed_and_entries,
    delete_feed,
    create_entries,
    mark_user_feeds_as_stale,
    get_feeds_for_refresh,
    check_and_create_user_feed,
)
from rss_reader.exceptions import URLValidationError
from rss_reader.helpers.urls import get_base_url

if TYPE_CHECKING:
    from rss_reader.models import Feed


def import_from_rss_urls(user, rss_urls: list[str]) -> str:
    """
    Requests urls and creates user feeds and entries.

    :param user: User
    :param rss_urls: List of urls
    :return: Error message
    """
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
                create_feed_and_entries(user, parsed_data)
            except URLValidationError as e:
                error_messages.append(f"{url}: {e.message}")

    error_message = "<br>".join(error_messages)

    return error_message


@transaction.atomic
def refresh_feed(
    feed: Feed,
    rss_data: RssParsedData,
    feed_has_entries: bool,
    request_result: RequestResult,
):
    """
    Updates everything related to Feed and its Entries,
    also deals with redirects, update intervals.
    """
    current_time = timezone.now()

    feed.etag = rss_data.feed_data["etag"]
    feed.modified = rss_data.feed_data["modified"]

    feed.last_updated = current_time
    feed.last_exception = request_result.error_message

    feed.last_response_body = None
    if request_result.status not in {200, 304}:
        # response body could have hint that we need to show to user
        feed.last_response_body = request_result.content

    old_entry_count = feed.entry_count
    if feed_has_entries:
        mark_user_feeds_as_stale(feed)
        create_entries(feed, rss_data)
    # we need to check this now, because response could just have stale entries
    # or entries that we filtered out
    new_entries = feed.entry_count > old_entry_count

    _change_feed_if_moved_or_disabled(feed, request_result)

    update_interval = _get_update_interval_in_hours(feed, new_entries, request_result)

    feed.update_interval = update_interval
    update_after = current_time + timedelta(hours=update_interval)
    update_after = update_after.replace(minute=0, second=0, microsecond=0)
    feed.update_after = update_after
    try:
        # transaction is necessary to create savepoint,
        # otherwise IntegrityError could roll back outer transaction
        with transaction.atomic():
            feed.save()
    except IntegrityError:
        # changing rss_url as a result of 301/308 permanent redirect can lead to merging two feeds into one
        delete_feed(feed)


def _change_feed_if_moved_or_disabled(feed: Feed, request_result: RequestResult):
    """
    Handles cases when Feed was moved temporarily or permanently, or stopped existing.
    """
    status = request_result.status
    headers = request_result.headers
    if status in {301, 308}:
        # moved permanently
        new_location = headers.get("Location")
        if new_location:
            feed.last_exception = f"Moved from {feed.rss_url} to {new_location}"
            feed.rss_url = new_location
    elif status in {302, 307}:
        new_location = headers.get("Location")
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


def _get_update_interval_in_hours(
    feed: Feed, new_entries: bool, request_result: RequestResult
) -> int:
    update_interval = feed.update_interval
    update_delay = get_update_delay_in_hours(request_result.headers)
    if update_delay:
        update_interval = update_delay
    else:
        if should_slow_down(
            request_result.status, new_entries, request_result.error_message
        ):
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
    return update_interval


def process_rss_url(request, rss_url: str):
    """
    Creates Feed by one RSS URL, done synchronously by user request

    :return: Error message
    """
    rss_url = rss_url.strip()
    user = request.user

    try:
        created = check_and_create_user_feed(rss_url, user)
    except URLValidationError as e:
        return e.message
    if created:
        # Done without errors
        return ""

    requests_results = asyncio.run(send_requests([RssUrlArgs(url=rss_url)]))
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
            create_feed_and_entries(user, parsed_data)
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


def extract_feed_urls_from_html(url: str, soup: BeautifulSoup) -> list[str]:
    """
    Trying to parse HTML page and get links to RSS feeds.

    :param url: URL that we suspect to be HTML page, used to resolve relative urls from that page
    :param soup: BeautifulSoup of a contents of a page
    :return: list of absolute RSS urls
    """
    rss_urls = set()
    for link in soup.find_all(
        "link", rel="alternate", type=("application/rss+xml", "application/atom+xml")
    ):
        href = link.get("href")
        if href:
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(url, href)
            rss_urls.add(href)

    for link in soup.find_all("link", rel="feed"):
        href = link.get("href")
        if href:
            # Resolve relative URLs if necessary
            if not href.startswith("http"):
                href = urljoin(url, href)
            rss_urls.add(href)

    rss_urls = list(rss_urls)
    return rss_urls


def refresh_feeds() -> str:
    """
    Refresh all feeds that are due to update.
    Used in background task.

    :return: Error message
    """
    feeds_by_urls = {}
    rss_urls_args = []
    feeds = get_feeds_for_refresh()
    site_urls_counter = Counter()
    for feed in feeds:
        site_url = get_base_url(feed.rss_url)

        feeds_by_urls[feed.rss_url] = feed
        rss_urls_args.append(
            RssUrlArgs(
                url=feed.rss_url,
                etag=feed.etag,
                modified=feed.modified,
                delay=site_urls_counter[site_url],
            )
        )
        site_urls_counter[site_url] += 1

    error_messages = []
    parsed_results = asyncio.run(fetch_and_parse_rss_urls(rss_urls_args))
    for request_result, parsed_data, feed_has_entries in parsed_results:
        error_message = request_result.error_message
        url = request_result.url
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        feed = feeds_by_urls[url]
        refresh_feed(feed, parsed_data, feed_has_entries, request_result)

    error_message = "<br>".join(error_messages)

    return error_message
