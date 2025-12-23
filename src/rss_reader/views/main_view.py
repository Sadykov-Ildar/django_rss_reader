from django.http import HttpResponse
from django.shortcuts import render

from rss_reader.repos.feed_repo import FeedRepo
from rss_reader.renderers.render_api import render_main_page
from rss_reader.forms import UploadFileForm
from rss_reader.use_cases.main import MainUseCase


def index_view(request):
    user = request.user

    feed_repo = FeedRepo()
    use_case = MainUseCase(feed_repo)

    user_feeds, feed, user_entries = use_case.get_main_page(user)

    content = render_main_page(
        request, user_feeds, user_feed=feed, user_entries=user_entries
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
