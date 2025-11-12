import datetime

from django.db import transaction
from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST

from rss_reader import opml_parser
from rss_reader.api.entry_api import mark_all_feeds_as_read, get_user_entries
from rss_reader.api.feed_api import (
    get_user_feeds,
    get_feeds_in_opml,
    get_user_feed_by_id,
)
from rss_reader.api.rss_api import process_rss_url
from rss_reader.api.render_api import render_feeds_and_entries, render_info_message
from rss_reader.forms import UploadFileForm
from rss_reader.models import UserFeed
from rss_reader.tasks import (
    refresh_feeds_task,
    import_from_rss_urls_task,
    create_favicons_task,
)


class FeedView(View):
    def post(self, request, *args, **kwargs):
        rss_url = request.POST.get("url")

        error_message = process_rss_url(request, rss_url)
        if error_message:
            return prepare_feed_error(request, error_message)

        create_favicons_task.delay()

        content = render_feeds_and_entries(request, add_form=True)

        return HttpResponse(content)

    def delete(self, request, user_feed_id, *args, **kwargs):
        with transaction.atomic():
            try:
                user_feed = get_user_feed_by_id(user_feed_id, request.user)
            except UserFeed.DoesNotExist:
                raise Http404

            get_user_entries(user=request.user).filter(
                entry__feed_id=user_feed.feed_id,
            ).delete()
            user_feed.delete()

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


def delete_all_user_feeds_view(request):
    with transaction.atomic():
        UserFeed.objects.filter(
            user=request.user,
        ).delete()

        get_user_entries(user=request.user).delete()

    return HttpResponse()


def add_feed_modal(request):
    context = {}
    return render(request, "rss_reader/add_new_feed_modal.html", context=context)


@require_POST
def import_feeds(request):
    form = UploadFileForm(request.POST, request.FILES)

    if form.is_valid():
        file = request.FILES["file"]

        document = opml_parser.from_string(file.read())

        rss_urls = []
        for outline in document:
            rss_urls.append(outline.xmlUrl)

        import_from_rss_urls_task.delay(request.user.id, rss_urls)

        content = render_info_message(
            request,
            info_message="Started background task to import feeds from file, refresh page later to see updates",
        )

        return HttpResponse(content)

    return HttpResponseForbidden()


def export_user_feeds_view(request):
    feeds = get_user_feeds(request.user).order_by("id")
    file_content = get_feeds_in_opml(feeds)
    filename = "rss_feeds-{}.opml".format(datetime.date.today().isoformat())

    response = HttpResponse(file_content, content_type="text/x-opml")
    response["Content-Disposition"] = "inline; filename=" + filename

    return response


def refresh_user_feeds(request):
    refresh_feeds_task.delay()

    content = render_info_message(
        request,
        info_message="Started background task to refresh user feeds, refresh page later to see updates",
    )
    return HttpResponse(content)


def mark_feeds_as_read_view(request):
    mark_all_feeds_as_read(request.user)

    content = render_feeds_and_entries(request)

    return HttpResponse(content)
