from django.db.models import QuerySet

from rss_reader._date import _get_datetime
from rss_reader.models import UserEntry, Entry, UserFeed


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
    ).select_related("entry")

    return user_entries


def _create_entries(feed, response):
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
    Entry.objects.bulk_create(entry_bulk_create, ignore_conflicts=True)

    feed.update_entry_count()
    feed.save()


def mark_entry_as_read(user_entry: UserEntry):
    user_entry.read = True
    user_entry.save()

    user_feed = UserFeed.objects.get(feed=user_entry.entry.feed_id)
    user_feed.update_read_count()
    user_feed.save()
