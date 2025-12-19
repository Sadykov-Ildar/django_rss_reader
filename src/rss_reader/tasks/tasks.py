import asyncio
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from rss_reader.api.rss_api import (
    import_from_rss_urls,
    refresh_feeds,
)
from rss_reader.repos.feed_repo import FeedRepo
from rss_reader.repos.request_history import delete_request_history_older_than
from rss_reader.tasks.favicons_api import (
    get_favicon_name_from_url,
    get_image_file_path,
    get_favicons,
)
from rss_reader.constants import (
    CACHE_FAVICON_PREFIX,
    CACHE_MUTEX_PREFIX,
    WS_TASKS_REFRESHED_GROUP_NAME,
)
from rss_reader.helpers.urls import get_base_url
from rss_reader.tasks.mutex import redis_lock


@shared_task(bind=True, name="rss_reader.refresh_feeds_task")
def refresh_feeds_task(self):
    """
    Background task for refreshing feeds, runs on schedule.
    """
    with redis_lock(CACHE_MUTEX_PREFIX + "refresh_feeds", 1) as acquired:
        if acquired:
            error_message = refresh_feeds()
        else:
            return "Task for refreshing feeds already started"

    message = "Feeds refreshed"
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        WS_TASKS_REFRESHED_GROUP_NAME, {"type": "tasks.refreshed", "message": message}
    )

    return error_message or "Refreshed successfully"


@shared_task(bind=True, name="rss_reader.import_from_rss_urls_task")
def import_from_rss_urls_task(self, user_id, rss_urls: list[str]) -> str:
    user = get_user_model().objects.get(id=user_id)
    result = import_from_rss_urls(user, rss_urls)
    create_favicons_task.delay()
    return result


@shared_task(bind=True, name="Creating favicons for feeds")
def create_favicons_task(self):
    """
    Background task for getting favicons for feeds, runs after importing feeds.
    """
    feed_repo = FeedRepo()
    feeds = feed_repo.get_feeds_with_unsearched_images()

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
    """
    Background task for clearing old request history, runs on schedule.
    """
    two_weeks_ago = timezone.now() - timedelta(days=14)
    delete_request_history_older_than(two_weeks_ago)
