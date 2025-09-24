from django.db.models import QuerySet
from feedparser import FeedParserDict

from rss_reader._date import _get_datetime
from rss_reader.models import UserEntry, Entry, UserFeed


def _create_user_entries(feed_id: int, user_id: int):
    entries_with_user_entries = UserEntry.objects.filter(
        user_id=user_id,
        entry__feed_id=feed_id,
    ).values_list("entry_id", flat=True)
    entries = Entry.objects.filter(feed_id=feed_id).exclude(
        id__in=entries_with_user_entries,
    )
    user_entries_bulk = [UserEntry(user_id=user_id, entry=entry) for entry in entries]
    UserEntry.objects.bulk_create(user_entries_bulk)


def _get_and_create_user_entries(user_feed: UserFeed) -> QuerySet[UserEntry]:
    if user_feed.stale:
        _create_user_entries(user_feed.feed_id, user_feed.user_id)
        user_feed.stale = False
        user_feed.save()

    user_entries = UserEntry.objects.filter(
        entry__feed_id=user_feed.feed_id,
    ).select_related("entry")

    return user_entries


def _create_entries(feed, response: FeedParserDict):
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
    Entry.objects.bulk_create(entry_bulk_create)


def get_user_entries_in_context(user_feed, start: int = 0):
    user_entries = _get_and_create_user_entries(user_feed)

    batch_size = 25
    more = False

    user_entries = user_entries.filter(
        id__gt=start,
    )[:batch_size]
    if len(user_entries) == batch_size:
        more = True
        start = list(user_entries)[-1].id

    context = {
        "user_feed": user_feed,
        "user_entries": user_entries,
        "more_entries": more,
        "entries_start": start,
    }
    return context
