from django.shortcuts import render
from django_celery_results.models import TaskResult

from rss_reader.api.feed_api import get_user_feeds
from rss_reader.api.render_api import render_main_page
from rss_reader.forms import UploadFileForm


def index_view(request):
    user = request.user

    # TODO: папка с непрочитанными статьями

    # TODO: группировка по папкам?
    user_feeds = get_user_feeds(user)
    return render_main_page(request, user_feeds, user_feeds[0])


def settings_view(request):
    user = request.user

    user_feeds = get_user_feeds(user)
    # TODO: таски нужно отображать в разрезе юзера
    tasks = TaskResult.objects.filter().order_by("-date_created")[:25]

    context = {
        "user_feeds": user_feeds,
        "file_import_form": UploadFileForm,
        "tasks": tasks,
    }
    return render(request, "rss_reader/settings.html", context=context)
