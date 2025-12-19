from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Subquery, OuterRef, Q
from django.utils import timezone

from rss_reader.constants import ENTRIES_BATCH_SIZE
from rss_reader.helpers.html_cleaner import clean_html, resolve_urls

from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, UserEntry, Entry
from vendoring.html_sanitizer.sanitizer import sanitize_html

if TYPE_CHECKING:
    from rss_reader.api.dtos import RssParsedData


@transaction.atomic
def create_feed_and_entries(user, rss_data: RssParsedData):
    """
    Create Feed and it's entries using parsed data.

    :raises URLValidationError:
    """
    feed_data = rss_data.feed_data

    try:
        feed = Feed.objects.create(
            site_url=feed_data["site_url"],
            rss_url=feed_data["rss_url"],
            title=feed_data["title"],
            subtitle=feed_data["subtitle"],
            author=feed_data["author"],
            etag=feed_data["etag"],
            modified=feed_data["modified"],
            feed_type=feed_data["feed_type"],
            image_url=feed_data["image_url"],
        )
    except IntegrityError as e:
        raise URLValidationError("Feed with this url already exists: " + str(e))
    create_entries(feed, rss_data)

    create_user_feed(feed, user)


def create_user_feed(feed: Feed, user):
    try:
        UserFeed.objects.create(user=user, feed=feed)
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")


def get_user_feed_by_id(pk: int, user) -> UserFeed | None:
    try:
        return UserFeed.objects.select_related("feed").get(pk=pk, user=user)
    except UserFeed.DoesNotExist:
        return None


def get_user_feed_by_user_entry(user_entry: UserEntry, user) -> UserFeed | None:
    try:
        user_feed = UserFeed.objects.select_related("feed").get(
            feed=user_entry.entry.feed_id, user=user
        )
    except UserFeed.DoesNotExist:
        user_feed = None

    return user_feed


def get_ordered_user_feeds(user) -> QuerySet[UserFeed]:
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


def get_user_feeds(user) -> QuerySet[UserFeed]:
    return UserFeed.objects.filter(
        user=user,
    )


def delete_feed(feed: Feed):
    feed.delete()


@transaction.atomic
def delete_user_feed(user_feed: UserFeed):
    get_user_entries(
        user=user_feed.user_id,
    ).filter(
        entry__feed_id=user_feed.feed_id,
    ).delete()

    user_feed.delete()


@transaction.atomic
def delete_user_feeds_for_user(user):
    get_user_feeds(user).delete()

    get_user_entries(user=user).delete()


def _create_user_entries(user_id: int):
    """
    Creates UserEntry for every Entry, if UserEntry didn't exist before.
    """
    entries_with_user_entries = get_user_entries(
        user=user_id,
    ).values_list("entry_id", flat=True)
    entries = Entry.objects.exclude(
        id__in=entries_with_user_entries,
    )
    user_entries_bulk = [UserEntry(user_id=user_id, entry=entry) for entry in entries]
    UserEntry.objects.bulk_create(user_entries_bulk, ignore_conflicts=True)


def _get_and_create_user_entries(user_feed: UserFeed) -> QuerySet[UserEntry]:
    """
    Creates UserEntry if needed, and returns UserEntries for UserFeed

    :param user_feed:
    :return:
    """
    if user_feed.stale:
        _create_user_entries(user_feed.user_id)
        user_feed.stale = False
        user_feed.save()

    user_entries = (
        get_user_entries(user_feed.user_id)
        .filter(entry__feed_id=user_feed.feed_id)
        .select_related("entry")
    )

    return user_entries


def filter_parsed_data(rss_data: RssParsedData, site_url: str):
    result = []
    entries_data = rss_data.entries
    for entry in entries_data:
        link = entry["link"]
        if "youtube.com/shorts/" in link:  # YouTube shorts are bad
            continue
        content = entry["content"]
        summary = entry["summary"]

        if content:
            if content.startswith(summary[:100]):
                # summary is often the same as content - skip it
                summary = ""

            content = clean_html(content)
            content = resolve_urls(content, site_url)
            content = sanitize_html(content, "utf-8", "text/html")

        if summary:
            summary = clean_html(summary)
            summary = resolve_urls(summary, site_url)
            summary = sanitize_html(summary, "utf-8", "text/html")

        entry["content"] = content
        entry["summary"] = summary

        result.append(entry)

    return result


def create_entries(feed: Feed, rss_data: RssParsedData):
    # update site_url in case it changed
    site_url = rss_data.feed_data["site_url"]
    if site_url and feed.site_url != site_url:
        feed.site_url = site_url

    entries_data = filter_parsed_data(rss_data, site_url)
    entry_bulk_create = []
    for record in reversed(entries_data):
        entry_bulk_create.append(
            Entry(
                feed=feed,
                link=record["link"],
                title=record["title"],
                published=record["published"],
                author=record["author"],
                content=record["content"],
                summary=record["summary"],
            )
        )
    Entry.objects.bulk_create(entry_bulk_create, ignore_conflicts=True)

    feed.update_entry_count()
    feed.save()


def mark_all_feeds_as_read(user):
    get_user_entries(user=user).update(read=True)

    # set read_count equal to feed.entry_count
    UserFeed.objects.filter(user_id=user).update(
        read_count=Subquery(
            UserFeed.objects.filter(pk=OuterRef("pk")).values("feed__entry_count")[:1]
        )
    )


def mark_user_feed_as_read(user_feed: UserFeed):
    get_user_entries(user_feed.user_id).filter(
        entry__feed=user_feed.feed_id,
    ).update(
        read=True,
    )
    user_feed.read_count = user_feed.feed.entry_count
    user_feed.save()


def mark_entry_as_read(user_entry: UserEntry, user_feed):
    user_entry.read = True
    user_entry.save()

    user_feed.update_read_count()
    user_feed.save()


def toggle_entry_read(user_entry: UserEntry, user_feed):
    user_entry.read = not user_entry.read
    user_entry.save()

    user_feed.update_read_count()
    user_feed.save()


def get_user_entries(user) -> QuerySet[UserEntry]:
    return UserEntry.objects.filter(
        user_id=user,
    )


def get_user_entry(user_entry_id: int, user) -> UserEntry | None:
    try:
        user_entry = (
            get_user_entries(
                user=user,
            )
            .filter(
                pk=user_entry_id,
            )
            .select_related("entry")
            .get()
        )
    except UserEntry.DoesNotExist:
        user_entry = None
    return user_entry


def get_filtered_user_entries(
    user_feed: UserFeed, search: str | None = None, start: datetime | None = None
) -> list[UserEntry]:
    user_entries = _get_and_create_user_entries(user_feed)
    if search:
        user_entries = user_entries.filter(
            Q(entry__title__icontains=search)
            | Q(entry__content__icontains=search)
            | Q(entry__summary__icontains=search)
        )

    if start:
        user_entries = user_entries.filter(entry__published__lt=start)

    user_entries = user_entries.order_by("read", "-entry__published")
    user_entries = user_entries[:ENTRIES_BATCH_SIZE]

    return list(user_entries)


def mark_user_feeds_as_stale(feed: Feed):
    UserFeed.objects.filter(feed=feed).update(stale=True)


def get_feeds_for_refresh():
    return Feed.objects.filter(
        updates_enabled=True,
    ).filter(Q(update_after__isnull=True) | Q(update_after__lt=timezone.now()))


def check_and_create_user_feed(rss_url: str, user) -> bool:
    """
    Validates URL, checks if feed for it already exists, creates UserFeed

    :param rss_url: RSS URL to check
    :param user: User
    :return: boolean flag, True if UserFeed was created, False otherwise
    :raises URLValidationError:
    """
    _validate_rss_url(user, rss_url)
    try:
        feed = Feed.objects.get(rss_url=rss_url)
    except Feed.DoesNotExist:
        created = False
    else:
        create_user_feed(feed, user)
        created = True

    return created


def _validate_rss_url(user, rss_url):
    """
    :raises URLValidationError:
    """
    if not rss_url:
        raise URLValidationError("Empty rss url")

    parsed_url = urlparse(rss_url)

    if not parsed_url.netloc:
        raise URLValidationError("Invalid URL")

    scheme = parsed_url.scheme
    if scheme not in ("http", "https"):
        raise URLValidationError("Url must start with http or https.")

    if get_user_feeds(user).filter(feed__rss_url=rss_url).exists():
        raise URLValidationError("Feed with this url already exists.")


def get_feeds_with_unsearched_images() -> QuerySet[Feed, Feed]:
    return Feed.objects.filter(searched_image_url=False)
