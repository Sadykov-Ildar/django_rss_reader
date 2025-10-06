from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404

from rss_reader.api.render_api import render_all, render_entries
from rss_reader.models import UserEntry, UserFeed


def entry_content_view(request, user_entry_id: int):
    try:
        user_entry = (
            UserEntry.objects.filter(pk=user_entry_id).select_related("entry").get()
        )
    except UserEntry.DoesNotExist:
        raise Http404

    user_entry.read = True
    user_entry.save()

    user_feed = UserFeed.objects.get(feed=user_entry.entry.feed_id)
    user_feed.update_read_count()
    user_feed.save()

    content = render_all(request, user_entry)

    return HttpResponse(content)


def entries_view(request, user_feed_id: int, start: int = 0):
    user_feed = get_object_or_404(UserFeed, id=user_feed_id)
    content = render_entries(request, user_feed, start)

    return HttpResponse(content)


def search_entries_view(request):
    # TODO: сделать поиск по статьям (по имени? по тексту?)
    search_query = request.POST.get("search")
    if search_query:
        pass
    return HttpResponse("Search results: " + search_query)
