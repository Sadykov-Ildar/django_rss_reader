import datetime

from django.http import HttpResponseForbidden, HttpResponse, Http404
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST

from rss_reader import opml_parser
from rss_reader.api.entry_api import mark_all_feeds_as_read, get_filtered_user_entries
from rss_reader.api.feed_api import (
    get_ordered_user_feeds,
    get_user_feed_by_id,
    delete_user_feed,
    delete_user_feeds_for_user,
)
from rss_reader.renderers.feeds_to_opml import get_feeds_in_opml
from rss_reader.api.rss_api import process_rss_url
from rss_reader.renderers.render_api import (
    render_feeds_and_entries,
    render_info_message,
)
from rss_reader.forms import UploadFileForm
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

        user_feeds = get_ordered_user_feeds(request.user)
        user_feed = None
        user_entries = []
        if user_feeds:
            user_feed = user_feeds[0]
            user_entries = get_filtered_user_entries(user_feed)
        content = render_feeds_and_entries(
            request,
            user_feeds,
            user_feed=user_feed,
            user_entries=user_entries,
            add_form=True,
        )

        return HttpResponse(content)

    def delete(self, request, user_feed_id, *args, **kwargs):
        user_feed = get_user_feed_by_id(user_feed_id, request.user)
        if user_feed is None:
            raise Http404

        delete_user_feed(user_feed)

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
    delete_user_feeds_for_user(request.user)

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
    feeds = get_ordered_user_feeds(request.user).order_by("id")
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

    user_feeds = get_ordered_user_feeds(request.user)

    user_feed = None
    user_entries = []
    if user_feeds:
        user_feed = user_feeds[0]
        user_entries = get_filtered_user_entries(user_feed)
    content = render_feeds_and_entries(
        request, user_feeds, user_feed=user_feed, user_entries=user_entries
    )

    return HttpResponse(content)
