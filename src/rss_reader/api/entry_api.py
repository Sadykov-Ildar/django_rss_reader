from django.db.models import QuerySet
from django.utils import timezone

from rss_reader.helpers.date_helpers import get_datetime
from rss_reader.helpers.html_cleaner import clean_html, resolve_urls
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
        user_id=user_feed.user_id,
    ).select_related("entry")

    return user_entries


def _create_entries(feed, response):
    entry_bulk_create = []
    for entry in reversed(response.get("entries", [])):
        link = entry.get("link", "")
        if "youtube.com/shorts/" in link: # YouTube shorts are bad
            continue
        content = entry.get("content")
        if content:
            # TODO: what to do if several contents exist?
            content = content[0]["value"]

            content = clean_html(content)
            content = resolve_urls(content, feed.site_url)

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
                summary=entry.get("description", ""),
            )
        )
    Entry.objects.bulk_create(entry_bulk_create, ignore_conflicts=True)

    feed.update_entry_count()
    feed.save()


def mark_all_feeds_as_read(user):
    # TODO: добавить возможность отмечать только одну статью прочитанной?
    UserEntry.objects.filter(
        user_id=user,
    ).update(
        read=True,
    )
    # TODO: не оптимально - попробовать одним запросом
    for user_feed in UserFeed.objects.filter(user_id=user):
        user_feed.update_read_count()
        user_feed.save()


def mark_user_feed_as_read(user_feed: UserFeed):
    UserEntry.objects.filter(
        entry__feed=user_feed.feed_id,
    ).update(
        read=True,
    )
    user_feed.update_read_count()
    user_feed.save()


def mark_entry_as_read(user_entry: UserEntry, user_feed):
    user_entry.read = True
    user_entry.save()

    user_feed.update_read_count()
    user_feed.save()
