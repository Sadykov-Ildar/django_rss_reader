from datetime import datetime

from django.http import Http404, HttpResponse

from rss_reader.repos.db_repo import FeedRepo
from rss_reader.renderers.render_api import (
    render_entry_content,
    render_entries,
    render_feed_and_entry,
    render_main_page,
)


def mark_entries_as_read_view(request, user_feed_id):
    feed_repo = FeedRepo()
    user_feed = feed_repo.get_user_feed_by_id(user_feed_id, request.user)
    if user_feed is None:
        raise Http404

    feed_repo.mark_user_feed_as_read(user_feed)

    user_entries = feed_repo.get_filtered_user_entries(user_feed)
    content = render_entries(request, user_feed, user_entries)

    return HttpResponse(content)


def entry_content_view(request, user_entry_id: int):
    feed_repo = FeedRepo()
    user_entry = feed_repo.get_user_entry(user_entry_id, request.user)
    if user_entry is None:
        raise Http404

    user_feed = feed_repo.get_user_feed_by_user_entry(user_entry, request.user)
    if user_feed is None:
        raise Http404

    feed_repo.mark_entry_as_read(user_entry, user_feed)

    if request.htmx:
        content = render_entry_content(request, user_entry, user_feed)
    else:
        user_feeds = feed_repo.get_ordered_user_feeds(request.user)
        user_entries = feed_repo.get_filtered_user_entries(user_feed)
        content = render_main_page(
            request,
            user_feeds,
            user_feed=user_feed,
            user_entries=user_entries,
            user_entry=user_entry,
        )
    return HttpResponse(content)


def toggle_entry_read_view(request, user_entry_id: int):
    feed_repo = FeedRepo()
    user_entry = feed_repo.get_user_entry(user_entry_id, request.user)
    if user_entry is None:
        raise Http404

    user_feed = feed_repo.get_user_feed_by_user_entry(user_entry, request.user)
    if user_feed is None:
        raise Http404

    feed_repo.toggle_entry_read(user_entry, user_feed)

    content = render_feed_and_entry(request, user_entry, user_feed)

    return HttpResponse(content)


def entries_view(request, user_feed_id: int, start: datetime | None = None):
    feed_repo = FeedRepo()
    user_feed = feed_repo.get_user_feed_by_id(user_feed_id, request.user)
    if user_feed is None:
        raise Http404

    search = request.GET.get("search", "")
    if request.htmx:
        user_entries = feed_repo.get_filtered_user_entries(user_feed, search, start)
        content = render_entries(request, user_feed, user_entries, start, search)
    else:
        user_feeds = feed_repo.get_ordered_user_feeds(request.user)
        user_entries = feed_repo.get_filtered_user_entries(user_feed)
        content = render_main_page(
            request,
            user_feeds,
            user_feed=user_feed,
            user_entries=user_entries,
            start=start,
            search=search,
        )

    return HttpResponse(content)
