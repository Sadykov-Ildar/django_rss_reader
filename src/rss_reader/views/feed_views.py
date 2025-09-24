from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.template import loader
from django.views import View

from rss_reader import opml_parser
from rss_reader._feed_api import _import_from_rss_urls, _refresh_user_feed
from rss_reader.exceptions import URLValidationError
from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed, UserEntry


class FeedView(View):
    def post(self, request, *args, **kwargs):
        rss_url = request.POST.get("url")

        error_messages, created_user_feeds = _import_from_rss_urls(
            request.user, [rss_url]
        )
        if error_messages:
            return prepare_feed_error(request, "\n\n".join(error_messages))

        context = {
            "user_feed": created_user_feeds[0],
        }
        content = loader.render_to_string(
            "rss_reader/add_feed_form.html", context, request
        )
        content += "\n\n"
        content += loader.render_to_string("rss_reader/oob_feed.html", context, request)

        return HttpResponse(content)

    def delete(self, request, user_feed_id, *args, **kwargs):
        with transaction.atomic():
            user_feed = get_object_or_404(UserFeed, pk=user_feed_id)
            user_feed.delete()
            # TODO: удалять ли Feed, если на него больше не ссылается ни один UserFeed?

            UserEntry.objects.filter(
                entry__feed_id=user_feed.feed_id, user=request.user
            ).delete()

        # TODO: возвращать список user_entry со следующего user_feed
        return HttpResponse()


def prepare_feed_error(request, error_message):
    context = {
        "error_message": error_message,
        "url": request.POST.get("url"),
    }
    return render(
        request,
        "rss_reader/add_feed_form.html",
        context=context,
        status=422,
    )


def import_feeds(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            file = request.FILES["file"]

            document = opml_parser.from_string(file.read())

            rss_urls = []
            for outline in document:
                rss_urls.append(outline.xmlUrl)

            error_messages, created_feeds = _import_from_rss_urls(
                request.user, rss_urls
            )

            context = {
                "feeds": sorted(created_feeds, key=lambda feed: feed.id, reverse=True),
                # TODO: это нужно отобразить. Или прервать загрузку, если появилась ошибка
                "error_message": "\n\n".join(error_messages),
            }
            content = loader.render_to_string("rss_reader/feeds.html", context, request)

            return HttpResponse(content)

    return HttpResponseForbidden()


def refresh_feeds(request):
    error_messages = []
    user = request.user

    user_feeds = UserFeed.objects.filter(user=user).select_related("feed")
    for user_feed in user_feeds:
        try:
            with transaction.atomic():
                _refresh_user_feed(user_feed.feed)
        except URLValidationError as e:
            error_messages.append(f"{user_feed.feed.rss_url}: {e.message}")

    context = {
        "error_message": "\n\n".join(error_messages),
    }
    content = loader.render_to_string("rss_reader/feeds.html", context, request)

    return HttpResponse(content)
