from urllib.parse import urlparse

import feedparser
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template import loader
from django.views import View

from rss_reader._feed_api import _create_feed_and_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed


class AddFeedView(View):
    def post(self, request, *args, **kwargs):
        rss_url = request.POST.get("url")
        try:
            self._validate_rss_url(rss_url)
        except URLValidationError as e:
            return prepare_feed_error(request, e.message)

        response: feedparser.FeedParserDict = feedparser.parse(rss_url)
        if response["bozo"]:
            return prepare_feed_error(
                request, "Some error occured: " + str(response["bozo_exception"])
            )

        try:
            with transaction.atomic():
                feed = _create_feed_and_entries(response)
        except URLValidationError as e:
            return prepare_feed_error(request, e.message)

        context = {
            "feed": feed,
        }
        content = loader.render_to_string(
            "rss_reader/add_feed_form.html", context, request
        )
        content += "\n\n\n"
        content += loader.render_to_string("rss_reader/oob-feed.html", context, request)

        return HttpResponse(content)

    @staticmethod
    def _validate_rss_url(rss_url):
        parsed_url = urlparse(rss_url)

        scheme = parsed_url.scheme
        if not parsed_url.netloc:
            raise URLValidationError("Invalid URL")
        if scheme not in ("http", "https"):
            raise URLValidationError("Url must start with http or https.")

        site_url = scheme + "://" + parsed_url.netloc + "/"
        if Feed.objects.filter(site_url=site_url).exists():
            raise URLValidationError("Feed with this url already exists.")


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


def delete_feed_view(request, feed_id):
    feed = get_object_or_404(Feed, pk=feed_id)
    feed.delete()

    return HttpResponse("deleted successfully")
