import asyncio
from collections import defaultdict, Counter
from datetime import timedelta
from pathlib import Path

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from rss_reader.api.rss_api import (
    import_from_rss_urls,
    refresh_feed,
    fetch_and_parse_rss_urls,
    RssUrlArgs,
)
from rss_reader.api.favicons_api import (
    get_favicon_name_from_url,
    get_image_file_path,
    get_favicons,
)
from rss_reader.constants import CACHE_FAVICON_PREFIX
from rss_reader.helpers.urls import get_base_url
from rss_reader.models import Feed, RequestHistory


# TODO: надо сделать так чтобы одновременно мог работать только один таск (https://docs.celeryq.dev/en/latest/tutorials/task-cookbook.html#ensuring-a-task-is-only-executed-one-at-a-time)
# TODO: использовать вебсокеты на случай если обновление произошло пока я что-то читаю
@shared_task(bind=True, name="rss_reader.refresh_feeds_task")
def refresh_feeds_task(self):
    feeds_by_urls = {}
    rss_urls_args = []
    feeds = Feed.objects.filter(
        updates_enabled=True,
    ).filter(Q(update_after__isnull=True) | Q(update_after__lt=timezone.now()))
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
        with transaction.atomic():
            refresh_feed(feed, parsed_data, feed_has_entries, request_result)

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
                image_name = get_favicon_name_from_url(site_url, image_url)
                image_path = get_image_file_path(image_name)
                if Path(image_path).exists():
                    feed.image.name = str(image_name)
                    feed.save()
            feed.searched_image_url = True
            feed.save()

    return "Created favicons for feeds"


@shared_task(bind=True, name="rss_reader.delete_old_request_history_records")
def delete_old_request_history_records(self):
    two_weeks_ago = timezone.now() - timedelta(days=14)
    RequestHistory.objects.filter(created_at__lt=two_weeks_ago).delete()
