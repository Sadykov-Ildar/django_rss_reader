from django.shortcuts import render

from rss_reader.api.feed_api import get_ordered_user_feeds
from rss_reader.api.render_api import render_main_page
from rss_reader.forms import UploadFileForm


def index_view(request):
    user = request.user
    user_feeds = get_ordered_user_feeds(user)
    return render_main_page(request, user_feeds, user_feeds[0])


def settings_view(request):
    user = request.user

    user_feeds = get_ordered_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/settings.html", context=context)
