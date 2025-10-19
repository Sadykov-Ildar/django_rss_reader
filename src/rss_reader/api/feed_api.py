from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from opml import OpmlDocument

from rss_reader.api.entry_api import _create_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed
from vendoring import fastfeedparser


def import_from_rss_urls(user, rss_urls: list[str]) -> str:
    error_messages = []

    # TODO: проверить на sql-иньекции, вставку путей к файлам, и всячески обезопасить,
    #  а также ограничить размер файла
    for rss_url in rss_urls:
        try:
            _validate_rss_url(user, rss_url)
            with transaction.atomic():
                _create_feed_and_entries(user, rss_url)
        except URLValidationError as e:
            error_messages.append(f"{rss_url}: {e.message}")

    error_message = "<br>".join(error_messages)

    return error_message


def _create_feed_and_entries(user, rss_url: str):
    try:
        feed = Feed.objects.get(rss_url=rss_url)
    except Feed.DoesNotExist:
        response, _ = __parse_feed(rss_url)

        feed_data: dict = response["feed"]

        try:
            # TODO: parsing?
            feed = Feed.objects.create(
                site_url=feed_data["link"],
                rss_url=rss_url,
                title=feed_data.get("title", ""),
                subtitle=feed_data.get("subtitle", ""),
                author=feed_data.get("author", ""),
                etag=response.get("etag") or "",
                modified=response.get("modified") or "",
                feed_type=response.get("feed_type", "rss"),
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


def refresh_feed(feed: Feed):
    response, new_entries_added = __parse_feed(
        feed.rss_url, etag=feed.etag, modified=feed.modified
    )

    feed.etag = response.get("etag", "") or ""
    feed.modified = response.get("modified", "") or ""
    feed.save()

    if new_entries_added:
        UserFeed.objects.filter(feed=feed).update(stale=True)

        _create_entries(feed, response)


def __parse_feed(rss_url, etag=None, modified=None):
    new_entries_added = False
    try:
        response = fastfeedparser.parse(rss_url, etag=etag, modified=modified)
        new_entries_added = True
    except (ValueError, HTTPError) as e:
        if e.code == 304:
            response = {
                "etag": e.headers.get("Etag") or "",
                "modified": e.headers.get("Last-modified") or "",
            }
        else:
            raise URLValidationError("Some error occured: " + str(e))
    except TimeoutError as e:
        raise URLValidationError("Time out: " + str(e))
    except URLError as e:
        raise URLValidationError("Error: " + str(e))

    return response, new_entries_added


def get_user_feeds(user):
    user_feeds = (
        UserFeed.objects.filter(
            user=user,
        )
        .select_related(
            "feed",
        )
        .order_by(
            "-pk",
        )
    )
    return user_feeds


def get_feeds_in_opml(user_feeds: QuerySet[UserFeed]) -> str:
    document = OpmlDocument(
        title="Django RSS Reader Subscriptions",
        date_created=timezone.now(),
    )
    for user_feed in user_feeds:
        feed = user_feed.feed
        document.add_outline(
            title=feed.title,
            text=feed.title,
            description=feed.subtitle,
            type=feed.feed_type,
            xml_url=feed.rss_url,
            html_url=feed.site_url,
        )
    file_content = str(document)

    return str(file_content)
