import feedparser
from django.db import IntegrityError

from rss_reader._date import _get_datetime
from rss_reader.models import Feed, Entry
from rss_reader.exceptions import URLValidationError


def _create_feed_and_entries(response: feedparser.FeedParserDict) -> Feed:
    feed_data: dict = response["feed"]
    try:
        # TODO: parsing?
        feed = Feed.objects.create(
            site_url=feed_data.get("link", ""),
            rss_url=feed_data.get("rss_url", ""),
            title=feed_data.get("title", ""),
            subtitle=feed_data.get("subtitle", ""),
            author=feed_data.get("author", ""),
            etag=response.get("etag", ""),
            modified=_get_datetime(response.get("modified_parsed")),
        )
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")

    entry_bulk_create = []
    for entry in response.get("entries", []):
        content = entry.get("content")
        if content and len(content) > 1:
            print("oopsie")
        if content:
            content = content[0]["value"]
        entry_bulk_create.append(
            Entry(
                feed=feed,
                # TODO: parsing?
                link=entry.get("link", ""),
                title=entry.get("title", ""),
                published=_get_datetime(entry.get("published_parsed")),
                author=entry.get("author", ""),
                content=content or "",
                summary=entry.get("summary", ""),
            )
        )

    Entry.objects.bulk_create(entry_bulk_create)

    return feed
