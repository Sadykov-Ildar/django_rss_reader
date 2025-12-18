from django.http import HttpResponse
from django.shortcuts import render

from rss_reader.repos.feed_repo import get_ordered_user_feeds, get_filtered_user_entries
from rss_reader.renderers.render_api import render_main_page
from rss_reader.forms import UploadFileForm


def index_view(request):
    user = request.user
    user_feeds = get_ordered_user_feeds(user)
    feed = None
    user_entries = []
    if user_feeds:
        feed = user_feeds[0]
        user_entries = get_filtered_user_entries(feed)
    content = render_main_page(
        request, user_feeds, user_feed=feed, user_entries=user_entries
    )
    return HttpResponse(content)


def settings_view(request):
    user = request.user

    user_feeds = get_ordered_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/settings.html", context=context)
