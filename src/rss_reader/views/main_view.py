from django.http import HttpResponse
from django.shortcuts import render

from rss_reader.repos.db_repo import FeedRepo
from rss_reader.renderers.render_api import render_main_page
from rss_reader.forms import UploadFileForm


def index_view(request):
    feed_repo = FeedRepo()
    user = request.user
    user_feeds = feed_repo.get_ordered_user_feeds(user)
    user_feed = None
    user_entries = []
    if user_feeds:
        user_feed = user_feeds[0]
        user_entries = feed_repo.get_filtered_user_entries(user_feed)
    content = render_main_page(
        request, user_feeds, user_feed=user_feed, user_entries=user_entries
    )
    return HttpResponse(content)


def settings_view(request):
    user = request.user
    feed_repo = FeedRepo()

    user_feeds = feed_repo.get_ordered_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/settings.html", context=context)
