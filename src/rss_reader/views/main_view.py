from django.shortcuts import render

from rss_reader.api.entry_api import get_user_entries_in_context
from rss_reader.models import UserFeed


def index_view(request):
    user = request.user

    user_feeds = UserFeed.objects.filter(
        user=user,
    ).order_by("-pk")

    context = {
        "user_feeds": user_feeds,
    }
    if user_feeds:
        user_entries_context = get_user_entries_in_context(user_feeds[0])
        context.update(user_entries_context)
    return render(request, "rss_reader/index.html", context=context)
