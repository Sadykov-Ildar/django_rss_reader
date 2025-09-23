from django.shortcuts import render

from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed, UserEntry


def index_view(request):
    # TODO: pagination, select_related
    user_feeds = UserFeed.objects.filter(
        user=request.user,
    ).order_by("-pk")

    if user_feeds:
        user_entries = UserEntry.objects.filter(
            entry__feed_id=user_feeds[0].feed_id,
        ).select_related("entry")
    else:
        user_entries = []

    context = {
        "file_import_form": UploadFileForm,
        "user_feeds": user_feeds,
        "user_entries": user_entries,
        "entry": user_entries[0].entry if user_entries else None,
    }
    return render(request, "rss_reader/index.html", context=context)
