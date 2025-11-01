from django.db.models import QuerySet, Subquery, OuterRef
from django.utils import timezone

from rss_reader.helpers.date_helpers import get_datetime
from rss_reader.helpers.html_cleaner import clean_html, resolve_urls
from rss_reader.models import UserEntry, Entry, UserFeed
from vendoring.html_sanitizer.sanitizer import sanitize_html


def _create_user_entries(user_id: int):
    entries_with_user_entries = UserEntry.objects.filter(
        user_id=user_id,
    ).values_list("entry_id", flat=True)
    entries = Entry.objects.exclude(
        id__in=entries_with_user_entries,
    )
    user_entries_bulk = [UserEntry(user_id=user_id, entry=entry) for entry in entries]
    UserEntry.objects.bulk_create(user_entries_bulk, ignore_conflicts=True)


def _get_and_create_user_entries(user_feed: UserFeed) -> QuerySet[UserEntry]:
    if user_feed.stale:
        _create_user_entries(user_feed.user_id)
        user_feed.stale = False
        user_feed.save()

    user_entries = UserEntry.objects.filter(
        entry__feed_id=user_feed.feed_id,
        user_id=user_feed.user_id,
    ).select_related("entry")

    return user_entries


def _create_entries(feed, parsed_data: dict):
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

    feed.update_entry_count()
    feed.save()


def mark_all_feeds_as_read(user):
    UserEntry.objects.filter(user_id=user).update(read=True)

    # set read_count equal to feed.entry_count
    UserFeed.objects.filter(user_id=user).update(
        read_count=Subquery(
            UserFeed.objects.filter(pk=OuterRef("pk")).values("feed__entry_count")[:1]
        )
    )


def mark_user_feed_as_read(user_feed: UserFeed):
    UserEntry.objects.filter(
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


def get_user_entry(user_entry_id: int) -> UserEntry:
    user_entry = (
        UserEntry.objects.filter(pk=user_entry_id).select_related("entry").get()
    )
    return user_entry
