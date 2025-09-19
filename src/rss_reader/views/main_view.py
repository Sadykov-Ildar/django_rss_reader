from django.shortcuts import render

from rss_reader.models import Feed, Entry


def index_view(request):
    # TODO: pagination, select_related
    feeds = Feed.objects.all().order_by("-pk")

    if feeds:
        entries = Entry.objects.filter(feed=feeds[0])
    else:
        entries = []

    context = {
        "feeds": feeds,
        "entries": entries,
        "entry": entries[0] if entries else None,
    }
    return render(request, "rss_reader/index.html", context=context)
