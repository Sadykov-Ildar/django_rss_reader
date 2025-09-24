from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template import loader

from rss_reader._entry_api import get_user_entries_in_context
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

    context = {
        "user_entry": user_entry,
        "entry": user_entry.entry,
    }
    content = loader.render_to_string("rss_reader/entry.html", context, request)
    content += "\n\n"
    content += loader.render_to_string(
        "rss_reader/oob_entry_content.html", context, request
    )
    return HttpResponse(content)


def entries_view(request, user_feed_id: int, start: int = 0):
    user_feed = get_object_or_404(UserFeed, id=user_feed_id)
    context = get_user_entries_in_context(user_feed, start)

    return render(request, "rss_reader/entries.html", context=context)
