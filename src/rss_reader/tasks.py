import asyncio
from collections import defaultdict
from typing import Iterable
from urllib.parse import urljoin

from aiohttp import ClientSession, ClientTimeout, ClientResponseError
from bs4 import BeautifulSoup
from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache

from rss_reader.api.feed_api import refresh_feed, import_from_rss_urls
from rss_reader.exceptions import URLValidationError
from rss_reader.helpers.urls import get_base_url
from rss_reader.models import Feed


CACHE_FAVICON_PREFIX = "favicon:"


@shared_task(bind=True, name="rss_reader.refresh_feeds_task")
def refresh_feeds_task(self):
    error_messages = []
    all_feeds = Feed.objects.all()
    for feed in all_feeds:
        try:
            with transaction.atomic():
                refresh_feed(feed)

        except URLValidationError as e:
            error_messages.append(f"{feed.rss_url}: {e.message}")

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
    feeds = Feed.objects.filter(image_url=None, searched_image_url=False)

    url_to_feeds = defaultdict(list)
    for feed in feeds:
        site_url = get_base_url(feed.rss_url)
        url_to_feeds[site_url].append(feed)

    urls_to_parse = set()
    favicon_urls_by_site_url = {}
    for url in url_to_feeds.keys():
        # TODO: этот кэш лучше хранить в БД
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
            soup = BeautifulSoup(await response.text(), "html.parser")

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
            async with session.head(
                favicon_url, allow_redirects=True, timeout=ClientTimeout(5)
            ) as response:
                if response.status == 200:
                    image_url = favicon_url
                    break

        # Fallback: Check for default /favicon.ico
        if image_url is None:
            default_favicon = urljoin(get_base_url(site_url), "/favicon.ico")
            async with session.head(
                default_favicon, allow_redirects=True, timeout=ClientTimeout(5)
            ) as response:
                if response.status == 200:
                    image_url = default_favicon

    except (ClientResponseError, TimeoutError):
        pass

    if image_url:
        cache.set(CACHE_FAVICON_PREFIX + site_url, image_url, timeout=0)

    return site_url, image_url
