from urllib.parse import urlparse

import feedparser
from django.db import IntegrityError, transaction

from rss_reader._date import _get_datetime
from rss_reader._entry_api import _create_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed


def _create_feed_and_entries(user, rss_url: str) -> UserFeed:
    try:
        feed = Feed.objects.get(rss_url=rss_url)
    except Feed.DoesNotExist:
        response: feedparser.FeedParserDict = feedparser.parse(rss_url)

        if response["bozo"]:
            raise URLValidationError(
                "Some error occured: " + str(response["bozo_exception"])
            )
        feed_data: dict = response["feed"]

        try:
            # TODO: parsing?
            feed = Feed.objects.create(
                site_url=feed_data["link"],
                rss_url=rss_url,
                title=feed_data.get("title", ""),
                subtitle=feed_data.get("subtitle", ""),
                author=feed_data.get("author", ""),
                etag=response.get("etag", ""),
                modified=_get_datetime(response.get("modified_parsed")),
            )
        except IntegrityError:
            raise URLValidationError("Feed with this url already exists.")
        _create_entries(feed, response)

    try:
        user_feed = UserFeed.objects.create(user=user, feed=feed)
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")

    return user_feed


def _validate_rss_url(user, rss_url):
    if not rss_url:
        raise URLValidationError("Empty rss url")

    parsed_url = urlparse(rss_url)

    if not parsed_url.netloc:
        raise URLValidationError("Invalid URL")

    scheme = parsed_url.scheme
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
        else:
            with transaction.atomic():
                try:
                    user_feed = _create_feed_and_entries(user, rss_url)
                    created_user_feeds.append(user_feed)
                except URLValidationError as e:
                    error_messages.append(f"{rss_url}: {e.message}")

    return error_messages, created_user_feeds


def _refresh_user_feed(feed: Feed):
    response: feedparser.FeedParserDict = feedparser.parse(
        feed.rss_url, etag=feed.etag, modified=feed.modified
    )

    if response["bozo"]:
        raise URLValidationError(
            "Some error occured: " + str(response["bozo_exception"])
        )

    feed.etag = response.get("etag", "")
    feed.modified = _get_datetime(response.get("modified_parsed"))
    feed.save()

    UserFeed.objects.filter(feed=feed).update(stale=True)

    _create_entries(feed, response)
