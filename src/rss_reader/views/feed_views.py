from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.template import loader
from django.views import View

from rss_reader import opml_parser
from rss_reader._feed_api import _import_from_rss_urls
from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed


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
        user_feed = get_object_or_404(UserFeed, pk=user_feed_id)
        user_feed.delete()
        # TODO: удалять ли Feed, если на него больше не ссылается ни один UserFeed?
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
