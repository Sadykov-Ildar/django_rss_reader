from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from rss_reader import opml_parser
from rss_reader.api.feed_api import import_from_rss_urls, refresh_feeds
from rss_reader.api.entry_api import mark_all_feeds_as_read
from rss_reader.api.render_api import render_feeds_and_entries
from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed, UserEntry


class FeedView(View):
    def post(self, request, *args, **kwargs):
        rss_url = request.POST.get("url")

        error_message = import_from_rss_urls(request.user, [rss_url])
        if error_message:
            return prepare_feed_error(request, error_message)

        content = render_feeds_and_entries(request, add_form=True)

        return HttpResponse(content)

    def delete(self, request, user_feed_id, *args, **kwargs):
        with transaction.atomic():
            user_feed = get_object_or_404(UserFeed, pk=user_feed_id)
            user_feed.delete()

            UserEntry.objects.filter(
                entry__feed_id=user_feed.feed_id,
                user=request.user,
            ).delete()

        content = render_feeds_and_entries(request)

        return HttpResponse(content)


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


def add_feed_modal(request):
    context = {
        "file_import_form": UploadFileForm,
    }
    return render(request, "rss_reader/add_new_feed_modal.html", context=context)


def import_feeds(request):
    if request.method == "POST":
        form = UploadFileForm(request.POST, request.FILES)

        if form.is_valid():
            file = request.FILES["file"]

            document = opml_parser.from_string(file.read())

            rss_urls = []
            for outline in document:
                rss_urls.append(outline.xmlUrl)

            error_message = import_from_rss_urls(request.user, rss_urls)

            content = render_feeds_and_entries(request, error_message)

            return HttpResponse(content)

    return HttpResponseForbidden()


def refresh_user_feeds(request):
    user = request.user

    error_message = refresh_feeds(user)

    content = render_feeds_and_entries(request, error_message)

    return HttpResponse(content)


def mark_feeds_as_read_view(request):
    mark_all_feeds_as_read(request.user)

    content = render_feeds_and_entries(request)

    return HttpResponse(content)
