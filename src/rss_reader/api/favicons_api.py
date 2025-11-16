import asyncio
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urljoin
from os.path import splitext

import aiofiles
from aiohttp import ClientResponse, ClientSession, ClientTimeout, ClientResponseError
from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache

from rss_reader.helpers.urls import get_base_url
from rss_reader.tasks import CACHE_FAVICON_PREFIX


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
                    image_name = get_favicon_name_from_url(site_url, image_url)
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
                    image_name = get_favicon_name_from_url(site_url, image_url)
                    image_path = get_image_file_path(image_name)
                    await save_image(image_path, response)

    except (ClientResponseError, TimeoutError):
        pass

    if image_url:
        cache.set(CACHE_FAVICON_PREFIX + site_url, image_url, timeout=0)

    return site_url, image_url


async def save_image(file_path, response: ClientResponse):
    async with aiofiles.open(file_path, mode="wb") as f:
        async for chunk in response.content.iter_chunked(8192):
            await f.write(chunk)


def get_favicon_name_from_url(site_url, url):
    # sometimes site_url and url are the same, sometimes not
    # base name from site_url
    base_name = urlparse(site_url).netloc.replace("/", "_").replace(".", "_")
    # extension from image_url
    _, image_ext = splitext(urlparse(url).path)
    path = base_name + image_ext
    filename = Path("favicons") / Path(path)
    return filename


def get_image_file_path(image_name):
    return settings.MEDIA_ROOT / image_name
