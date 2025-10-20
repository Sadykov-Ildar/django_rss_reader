from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction

from rss_reader.api.feed_api import refresh_feed, import_from_rss_urls
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed


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
    return import_from_rss_urls(user, rss_urls)
