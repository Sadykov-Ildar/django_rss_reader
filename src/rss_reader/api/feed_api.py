from urllib.parse import urlparse

import feedparser
from django.db import IntegrityError, transaction

from rss_reader._date import _get_datetime
from rss_reader.api.entry_api import _create_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed


def import_from_rss_urls(user, rss_urls: list[str]) -> str:
    error_messages = []

    for rss_url in rss_urls:
        try:
            _validate_rss_url(user, rss_url)
            with transaction.atomic():
                _create_feed_and_entries(user, rss_url)
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")

    error_message = "\n\n".join(error_messages)

    return error_message


def refresh_feeds(user) -> str:
    error_messages = []
    user_feeds = UserFeed.objects.filter(user=user).select_related("feed")
    for user_feed in user_feeds:
        try:
            with transaction.atomic():
                _refresh_user_feed(user_feed.feed)
        except URLValidationError as e:
            error_messages.append(f"{user_feed.feed.rss_url}: {e.message}")

    error_message = "\n\n".join(error_messages)

    return error_message


def _create_feed_and_entries(user, rss_url: str):
    try:
        feed = Feed.objects.get(rss_url=rss_url)
    except Feed.DoesNotExist:
        response = __parse_feed(rss_url)

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
        UserFeed.objects.create(user=user, feed=feed)
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")


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


def _refresh_user_feed(feed: Feed):
    response = __parse_feed(feed.rss_url, etag=feed.etag, modified=feed.modified)

    if response["bozo"]:
        raise URLValidationError(
            "Some error occured: " + str(response["bozo_exception"])
        )

    feed.etag = response.get("etag", "")
    feed.modified = _get_datetime(response.get("modified_parsed"))
    feed.save()

    UserFeed.objects.filter(feed=feed).update(stale=True)

    _create_entries(feed, response)


def __parse_feed(rss_url, etag=None, modified=None):
    return feedparser.parse(rss_url, etag=etag, modified=modified)
