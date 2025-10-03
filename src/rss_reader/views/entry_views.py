from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from rss_reader.api.entry_api import get_user_entries_in_context
from rss_reader.api.render_api import render_all
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

    return render_all(request, user_entry)


def entries_view(request, user_feed_id: int, start: int = 0):
    # TODO: как-то выделять выбранный feed
    user_feed = get_object_or_404(UserFeed, id=user_feed_id)
    context = get_user_entries_in_context(user_feed, start)

    return render(request, "rss_reader/entries.html", context=context)


def search_entries_view(request):
    # TODO: сделать поиск по статьям (по имени? по тексту?)
    search_query = request.POST.get("search")
    if search_query:
        pass
    return HttpResponse("Search results: " + search_query)
