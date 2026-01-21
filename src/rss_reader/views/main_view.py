from django.http import HttpResponse
from django.shortcuts import render

from rss_reader.repos import db_repo
from rss_reader.renderers.render_html import render_main_page
from rss_reader.forms import UploadFileForm


def index_view(request):
    user = request.user
    user_feeds = db_repo.get_ordered_user_feeds(user)
    user_feed = None
    user_entries = []
    if user_feeds:
        user_feed = user_feeds[0]
        user_entries = db_repo.get_filtered_user_entries(user_feed)
    content = render_main_page(
        request, user_feeds, user_feed=user_feed, user_entries=user_entries
    )
    return HttpResponse(content)


def settings_view(request):
    user = request.user

    user_feeds = db_repo.get_ordered_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/settings.html", context=context)
