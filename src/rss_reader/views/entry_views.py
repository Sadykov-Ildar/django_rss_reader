from django.shortcuts import get_object_or_404, render

from rss_reader.models import Entry


def entry_content_view(request, entry_id: int):
    entry = get_object_or_404(Entry, id=entry_id)

    context = {
        "entry": entry,
    }
    return render(request, "rss_reader/entry_content.html", context=context)


def entries_view(request, feed_id: int):
    entries = Entry.objects.filter(feed_id=feed_id)

    context = {
        "entries": entries,
    }
    return render(request, "rss_reader/entries.html", context=context)
