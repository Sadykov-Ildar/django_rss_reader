import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin

from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from bs4 import BeautifulSoup
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from rss_reader.api.rss_api import (
    import_from_rss_urls,
    refresh_feed,
    fetch_and_parse_rss_urls,
    RssUrlArgs,
)
from rss_reader.helpers.file_paths import (
    save_image,
    get_favicon_name_from_url,
    get_image_file_path,
)
from rss_reader.helpers.urls import get_base_url
from rss_reader.models import Feed


CACHE_FAVICON_PREFIX = "favicon:"


@shared_task(bind=True, name="rss_reader.refresh_feeds_task")
def refresh_feeds_task(self):
    # TODO: automatically slow down polling rates for feeds that update rarely
    #  and if feed stops returning feed data - stop polling
    # TODO: tell user if feed died
    # TODO: check Retry-After, max-age=, and other stuff
    # TODO: rss has different tags for hints as to when is a bad time to poll for updates
    # TODO: don't start multiple requests to the same server at the same time, give the server a break
    # TODO: https://rachelbythebay.com/frb/

    feeds_by_urls = {}
    rss_urls_args = []
    for feed in Feed.objects.all():
        feeds_by_urls[feed.rss_url] = feed
        rss_urls_args.append(
            RssUrlArgs(
                url=feed.rss_url,
                etag=feed.etag,
                modified=feed.modified,
            )
        )

    error_messages = []
    parsed_results = asyncio.run(fetch_and_parse_rss_urls(rss_urls_args))
    for request_result, parsed_data, new_entries_added in parsed_results:
        error_message = request_result.error_message
        url = request_result.url
        if error_message:
            error_messages.append(f"{url}: {error_message}")
        else:
            feed = feeds_by_urls[url]
            with transaction.atomic():
                refresh_feed(feed, parsed_data, new_entries_added, request_result)

    error_message = "<br>".join(error_messages)

    return error_message or "Refreshed successfully"


@shared_task(bind=True, name="rss_reader.import_from_rss_urls_task")
def import_from_rss_urls_task(self, user_id, rss_urls: list[str]) -> str:
    user = get_user_model().objects.get(id=user_id)
    result = import_from_rss_urls(user, rss_urls)
    create_favicons_task.delay()
    return result


@shared_task(bind=True, name="Creating favicons for feeds")
def create_favicons_task(self):
    # TODO: можно сделать попроще
    # TODO: можно сперва поискать в файловой системе по урлу, и только потом - скачивать
    feeds = Feed.objects.filter(searched_image_url=False)

    url_to_feeds = defaultdict(list)
    for feed in feeds:
        site_url = get_base_url(feed.rss_url)
        url_to_feeds[site_url].append(feed)

    urls_to_parse = set()
    favicon_urls_by_site_url = {}
    for url in url_to_feeds.keys():
        result_url = cache.get(CACHE_FAVICON_PREFIX + url)
        if result_url:
            favicon_urls_by_site_url[url] = result_url
        else:
            urls_to_parse.add(url)

    results = asyncio.run(get_favicons(urls_to_parse))
    favicon_urls_by_site_url.update(dict(results))

    for site_url, image_url in favicon_urls_by_site_url.items():
        _feeds = url_to_feeds[site_url]
        for feed in _feeds:
            if image_url:
                feed.image_url = image_url
                image_name = get_favicon_name_from_url(image_url)
                image_path = get_image_file_path(image_name)
                if Path(image_path).exists():
                    feed.image.name = str(image_name)
                    feed.save()
            feed.searched_image_url = True
            feed.save()

    return "Created favicons for feeds"


async def get_favicons(urls: Iterable[str]) -> list[tuple[str, str]]:
    async with ClientSession(timeout=ClientTimeout(10)) as session:
        return await asyncio.gather(*(get_favicon_url(session, url) for url in urls))


async def get_favicon_url(session, site_url):
    """Fetch favicon URL from the website."""
    image_url = None
    try:
        async with session.get(site_url) as response:
            response.raise_for_status()
            soup = BeautifulSoup(await response.text(), "lxml")

        # Find all favicon-related link tags
        favicon_tags = soup.find_all(
            "link", rel=["icon", "shortcut icon", "apple-touch-icon"]
        )

        # Collect all favicon URLs
        favicon_urls = []
        for tag in favicon_tags:
            href = tag.get("href")
            if href:
                favicon_urls.append(urljoin(site_url, href))

        for favicon_url in favicon_urls:
            async with session.get(
                favicon_url, allow_redirects=True, timeout=ClientTimeout(5)
            ) as response:
                if response.status == 200:
                    image_url = favicon_url
                    image_name = get_favicon_name_from_url(image_url)
                    image_path = get_image_file_path(image_name)
                    await save_image(image_path, response)
                    break

        # Fallback: Check for default /favicon.ico
        if image_url is None:
            default_favicon = urljoin(get_base_url(site_url), "/favicon.ico")
            async with session.get(
                default_favicon, allow_redirects=True, timeout=ClientTimeout(5)
            ) as response:
                if response.status == 200:
                    image_url = default_favicon
                    image_name = get_favicon_name_from_url(image_url)
                    image_path = get_image_file_path(image_name)
                    await save_image(image_path, response)

    except (ClientResponseError, TimeoutError):
        pass

    if image_url:
        cache.set(CACHE_FAVICON_PREFIX + site_url, image_url, timeout=0)

    return site_url, image_url
