from datetime import datetime

from django.http import Http404, HttpResponse

from rss_reader.api.entry_api import (
    mark_entry_as_read,
    mark_user_feed_as_read,
    toggle_entry_read,
    get_user_entry,
)
from rss_reader.api.feed_api import (
    get_user_feeds,
    get_user_feed_by_id,
    get_user_feed_by_feed_id,
)
from rss_reader.api.render_api import (
    render_entry_content,
    render_entries,
    render_feed_and_entry,
    render_main_page,
)
from rss_reader.models import UserEntry, UserFeed


def mark_entries_as_read_view(request, user_feed_id):
    try:
        user_feed = UserFeed.objects.select_related("feed").get(id=user_feed_id)
    except UserFeed.DoesNotExist:
        raise Http404

    mark_user_feed_as_read(user_feed)

    content = render_entries(request, user_feed)

    return HttpResponse(content)


def entry_content_view(request, user_entry_id: int):
    try:
        user_entry = get_user_entry(user_entry_id, request.user)
    except UserEntry.DoesNotExist:
        raise Http404

    try:
        user_feed = get_user_feed_by_feed_id(user_entry.entry.feed_id, request.user)
    except UserFeed.DoesNotExist:
        raise Http404

    mark_entry_as_read(user_entry, user_feed)

    if request.htmx:
        content = render_entry_content(request, user_entry, user_feed)
        return HttpResponse(content)
    else:
        user_feeds = get_user_feeds(request.user)
        return render_main_page(request, user_feeds, user_feed, user_entry=user_entry)


def toggle_entry_read_view(request, user_entry_id: int):
    try:
        user_entry = get_user_entry(user_entry_id, request.user)
    except UserEntry.DoesNotExist:
        raise Http404

    try:
        user_feed = get_user_feed_by_feed_id(user_entry.entry.feed_id, request.user)
    except UserFeed.DoesNotExist:
        raise Http404

    toggle_entry_read(user_entry, user_feed)

    content = render_feed_and_entry(request, user_entry, user_feed)

    return HttpResponse(content)


def entries_view(request, user_feed_id: int, start: datetime = None):
    try:
        user_feed = get_user_feed_by_id(user_feed_id, request.user)
    except UserFeed.DoesNotExist:
        raise Http404
    # TODO: нужен поиск по всем фидам
    # TODO: и что-то придумать с сабстаком и другими фидами, где страницы нужно подгружать постоянно
    search = request.GET.get("search")
    if request.htmx:
        content = render_entries(request, user_feed, start, search)
        return HttpResponse(content)
    else:
        user_feeds = get_user_feeds(request.user)
        return render_main_page(
            request, user_feeds, user_feed, start=start, search=search
        )
