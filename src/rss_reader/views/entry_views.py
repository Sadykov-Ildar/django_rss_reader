from datetime import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from rss_reader.api.entry_api import mark_entry_as_read, mark_user_feed_as_read
from rss_reader.api.render_api import render_entry_content, render_entries
from rss_reader.models import UserEntry, UserFeed


def mark_entries_as_read_view(request, user_feed_id):
    user_feed = get_object_or_404(UserFeed, id=user_feed_id)

    mark_user_feed_as_read(user_feed)

    content = render_entries(request, user_feed)

    return HttpResponse(content)


def entry_content_view(request, user_entry_id: int):
    try:
        user_entry = (
            UserEntry.objects.filter(pk=user_entry_id).select_related("entry").get()
        )
    except UserEntry.DoesNotExist:
        raise Http404

    try:
        user_feed = UserFeed.objects.get(
            user=request.user,
            feed=user_entry.entry.feed_id,
        )
    except UserFeed.DoesNotExist:
        raise Http404

    mark_entry_as_read(user_entry, user_feed)

    content = render_entry_content(request, user_entry, user_feed)

    return HttpResponse(content)


def entries_view(request, user_feed_id: int, start: datetime = None):
    user_feed = get_object_or_404(UserFeed, id=user_feed_id)
    content = render_entries(request, user_feed, start)

    return HttpResponse(content)


@require_POST
def search_entries_view(request):
    # TODO: сделать поиск по статьям (по имени? по тексту?)
    search_query = request.POST.get("search")
    if search_query:
        pass
    return HttpResponse("Search results: " + search_query)
