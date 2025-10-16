from celery import shared_task
from django.db import transaction

from rss_reader.api.feed_api import refresh_feed
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed


@shared_task(bind=True)
def refresh_feeds_task(self):
    error_messages = []
    all_feeds = Feed.objects.all()
    for feed in all_feeds:
        try:
            with transaction.atomic():
                refresh_feed(feed)

        except URLValidationError as e:
            error_messages.append(f"{feed.rss_url}: {e.message}")

    error_message = "\n\n".join(error_messages)

    return error_message
