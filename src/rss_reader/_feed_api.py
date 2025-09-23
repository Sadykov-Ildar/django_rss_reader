from urllib.parse import urlparse

import feedparser
from django.db import IntegrityError, transaction
from feedparser import FeedParserDict

from rss_reader._date import _get_datetime
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, Entry, UserFeed, UserEntry


def _create_feed_and_entries(user, response: feedparser.FeedParserDict) -> UserFeed:
    feed_data: dict = response["feed"]

    site_url = feed_data["link"]
    feed_created = True
    try:
        feed = Feed.objects.get(site_url=site_url)
        feed_created = False
    except Feed.DoesNotExist:
        try:
            # TODO: parsing?
            feed = Feed.objects.create(
                site_url=site_url,
                rss_url=feed_data.get("rss_url", ""),
                title=feed_data.get("title", ""),
                subtitle=feed_data.get("subtitle", ""),
                author=feed_data.get("author", ""),
                etag=response.get("etag", ""),
                modified=_get_datetime(response.get("modified_parsed")),
            )
        except IntegrityError:
            raise URLValidationError("Feed with this url already exists.")

    try:
        user_feed = UserFeed.objects.create(user=user, feed=feed)
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")

    if feed_created:
        entries = _create_entries(feed, response, user)
    else:
        entries = Entry.objects.filter(feed=feed)

    user_entries_bulk = [UserEntry(user=user, entry=entry) for entry in entries]
    UserEntry.objects.bulk_create(user_entries_bulk)

    return user_feed


def _create_entries(feed, response: FeedParserDict, user) -> list[Entry]:
    entry_bulk_create = []
    for entry in response.get("entries", []):
        content = entry.get("content")
        if content:
            # TODO: what to do if several contents exist?
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
    entries = Entry.objects.bulk_create(entry_bulk_create)
    return entries


def _validate_rss_url(user, rss_url):
    parsed_url = urlparse(rss_url)

    scheme = parsed_url.scheme
    if not parsed_url.netloc:
        raise URLValidationError("Invalid URL")
    if scheme not in ("http", "https"):
        raise URLValidationError("Url must start with http or https.")

    site_url = scheme + "://" + parsed_url.netloc + "/"
    if UserFeed.objects.filter(user=user, feed__site_url=site_url).exists():
        raise URLValidationError("Feed with this url already exists.")


def _import_from_rss_urls(
    user, rss_urls: list[str]
) -> tuple[list[str], list[UserFeed]]:

    error_messages = []
    created_user_feeds = []

    for rss_url in rss_urls:
        try:
            _validate_rss_url(user, rss_url)
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")

        response: feedparser.FeedParserDict = feedparser.parse(rss_url)
        if response["bozo"]:
            error_messages.append(
                f"{rss_url}: "
                + "Some error occured: "
                + str(response["bozo_exception"])
            )

        with transaction.atomic():
            try:
                user_feed = _create_feed_and_entries(user, response)
                created_user_feeds.append(user_feed)
            except URLValidationError as e:
                error_messages.append(f"{rss_url}: {e.message}")

    return error_messages, created_user_feeds
