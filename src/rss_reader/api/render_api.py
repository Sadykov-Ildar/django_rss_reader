from django.http import HttpResponse
from django.template import loader

from rss_reader.api.entry_api import get_user_entries_in_context
from rss_reader.models import UserFeed


def render_feeds_and_entries(request, error_message="", add_form=False):
    user_feeds = UserFeed.objects.filter(
        user=request.user,
    ).order_by("-pk")

    context = {
        "user_feeds": user_feeds,
        "error_message": error_message,
    }

    if user_feeds:
        context.update(get_user_entries_in_context(user_feeds[0]))

    content = loader.render_to_string("rss_reader/oob_entries.html", context, request)
    content += "\n\n"
    content += loader.render_to_string("rss_reader/oob_feeds.html", context, request)

    if add_form:
        content += "\n\n"
        content += loader.render_to_string(
            "rss_reader/add_feed_form.html", context, request
        )
    return HttpResponse(content)


def render_all(request, user_entry):

    user_feeds = UserFeed.objects.filter(
        user=request.user,
    ).order_by("-pk")

    context = {
        "user_feeds": user_feeds,
        "user_entry": user_entry,
        "entry": user_entry.entry,
    }
    content = loader.render_to_string("rss_reader/entry.html", context, request)
    content += "\n\n"
    content += loader.render_to_string(
        "rss_reader/oob_entry_content.html", context, request
    )
    content += "\n\n"
    content += loader.render_to_string("rss_reader/oob_feeds.html", context, request)

    return HttpResponse(content)
