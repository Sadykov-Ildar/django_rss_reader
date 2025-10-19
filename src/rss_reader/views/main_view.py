from django.shortcuts import render

from rss_reader.api.feed_api import get_user_feeds
from rss_reader.api.render_api import get_user_entries_in_context
from rss_reader.forms import UploadFileForm


def index_view(request):
    user = request.user

    # TODO: папка с непрочитанными статьями

    # TODO: группировка по папкам?
    user_feeds = get_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
    }
    if user_feeds:
        user_entries_context = get_user_entries_in_context(user_feeds[0])
        context.update(user_entries_context)
    return render(request, "rss_reader/index.html", context=context)


def settings_view(request):
    user = request.user

    user_feeds = get_user_feeds(user)

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/settings.html", context=context)
