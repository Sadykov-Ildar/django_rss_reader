from django.shortcuts import render

from rss_reader._entry_api import _get_and_create_user_entries
from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed


def index_view(request):
    user = request.user
    user_entries = []

    user_feeds = UserFeed.objects.filter(
        user=user,
    ).order_by("-pk")

    if user_feeds:
        user_entries = _get_and_create_user_entries(user_feeds[0])

    context = {
        "file_import_form": UploadFileForm,
        "user_feeds": user_feeds,
        "user_entries": user_entries,
        "entry": user_entries[0].entry if user_entries else None,
    }
    return render(request, "rss_reader/index.html", context=context)
