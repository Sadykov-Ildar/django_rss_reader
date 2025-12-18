from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Subquery, OuterRef, Q
from django.utils import timezone

from rss_reader.constants import ENTRIES_BATCH_SIZE
from rss_reader.helpers.date_helpers import get_datetime
from rss_reader.helpers.html_cleaner import clean_html, resolve_urls

from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, UserEntry, Entry
from vendoring.html_sanitizer.sanitizer import sanitize_html


@transaction.atomic
def create_feed_and_entries(user, rss_url: str, parsed_data: dict):
    """
    Create Feed and it's entries using parsed data.

    :raises URLValidationError:
    """
    feed_data: dict = parsed_data["feed"]
    image_url = feed_data.get("image_url")

    try:
        feed = Feed.objects.create(
            site_url=feed_data["link"],
            rss_url=rss_url,
            title=feed_data.get("title", ""),
            subtitle=feed_data.get("subtitle", ""),
            author=feed_data.get("author", ""),
            etag=parsed_data.get("etag") or "",
            modified=parsed_data.get("modified") or "",
            feed_type=parsed_data.get("feed_type", "rss"),
            image_url=image_url,
        )
    except IntegrityError as e:
        raise URLValidationError("Feed with this url already exists: " + str(e))
    _create_entries(feed, parsed_data)

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


# TODO: это бы как-то поправить
def _create_entries(feed: Feed, parsed_data: dict):
    entry_bulk_create = []
    for entry in reversed(parsed_data.get("entries", [])):
        link = entry.get("link", "")
        if "youtube.com/shorts/" in link:  # YouTube shorts are bad
            continue
        content = entry.get("content")
        summary = entry.get("description", "")

        if content:
            content = content[0]["value"]
            if content.startswith(summary[:100]):
                # summary is often the same as content - skip it
                summary = ""

            content = clean_html(content)
            content = resolve_urls(content, feed.site_url)
            content = sanitize_html(content, "utf-8", "text/html")

        if summary:
            summary = clean_html(summary)
            summary = resolve_urls(summary, feed.site_url)
            summary = sanitize_html(summary, "utf-8", "text/html")

        published = get_datetime(entry.get("published"))
        if published is None:
            published = timezone.now()
        entry_bulk_create.append(
            Entry(
                feed=feed,
                link=entry.get("link", ""),
                title=entry.get("title", ""),
                published=published,
                author=entry.get("author", ""),
                content=content or "",
                summary=summary,
            )
        )
    Entry.objects.bulk_create(entry_bulk_create, ignore_conflicts=True)

    # update site_url in case it changed
    site_url = parsed_data.get("feed", {}).get("link")
    if site_url and feed.site_url != site_url:
        feed.site_url = site_url

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
        user_entries = user_entries.filter(
            entry__published__lt=start,
        )

    user_entries = user_entries.order_by("read", "-entry__published")[
        :ENTRIES_BATCH_SIZE
    ]
    return list(user_entries)
