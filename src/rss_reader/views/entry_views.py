from datetime import datetime

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

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
    # TODO: нужен поиск по всем фидам
    # TODO: а еще нужно добавить игнор записей shorts из ютуба
    # TODO: и что-то придумать с сабстаком и другими фидами, где страницы нужно подгружать постоянно
    # TODO: иконки фидам как-нибудь добавить бы
    search = request.GET.get("search")
    content = render_entries(request, user_feed, start, search)

    return HttpResponse(content)
