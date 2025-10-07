from datetime import datetime

from django.http import Http404
from django.template import loader

from rss_reader.api.entry_api import _get_and_create_user_entries
from rss_reader.models import UserFeed, UserEntry


class FeedsRenderer:
    def __init__(self, request, context=None, separator="\n\n"):
        self.request = request
        self.context = context or {}
        self._content = ""
        self.separator = separator

    def get_result(self):
        return self._content

    def include_feed(self):
        self._render_template("rss_reader/oob_feed.html")

    def include_feeds(self):
        self._render_template("rss_reader/oob_feeds.html")

    def include_entries(self):
        self._render_template("rss_reader/entries.html")

    def include_oob_entries(self):
        self._render_template("rss_reader/oob_entries.html")

    def include_entry_content(self):
        self._render_template("rss_reader/entry.html")
        self._render_template("rss_reader/oob_entry_content.html")

    def include_add_feed_form(self):
        self._render_template("rss_reader/add_feed_form.html")

    def include_error_message(self):
        # TODO: ошибки часто никак не отображаются, может вынести их в модальное окно?
        self._render_template("rss_reader/error_message.html")

    def _render_template(self, template_name):
        self._content += self.separator
        self._content += loader.render_to_string(
            template_name, self.context, self.request
        )


def render_feeds_and_entries(request, error_message="", add_form=False):
    user_feeds = UserFeed.objects.filter(
        user=request.user,
    ).order_by("-pk")

    context = {
        "user_feeds": user_feeds,
        # TODO: ошибки часто никак не отображаются, может вынести их в модальное окно?
        "error_message": error_message,
    }

    if user_feeds:
        context.update(get_user_entries_in_context(user_feeds[0]))

    renderer = FeedsRenderer(request, context)
    renderer.include_feeds()
    renderer.include_oob_entries()
    if add_form:
        renderer.include_add_feed_form()

    return renderer.get_result()


def render_entry_content(request, user_entry: UserEntry):
    try:
        user_feed = UserFeed.objects.get(feed=user_entry.entry.feed_id)
    except UserFeed.DoesNotExist:
        raise Http404

    entry_summary = user_entry.entry.summary
    entry_content = user_entry.entry.content
    need_summary = bool(entry_summary)
    if entry_content.startswith(entry_summary):
        need_summary = False

    context = {
        "user_entry": user_entry,
        "entry": user_entry.entry,
        "need_summary": need_summary,
        "active_entry": user_entry,
        "active_feed": user_feed,
        "user_feed": user_feed,
    }

    renderer = FeedsRenderer(request, context)
    renderer.include_feed()
    renderer.include_entry_content()

    return renderer.get_result()


def render_entries(request, user_feed: UserFeed, start: datetime):
    context = get_user_entries_in_context(user_feed, start)

    renderer = FeedsRenderer(request, context)
    renderer.include_entries()
    renderer.include_feed()

    return renderer.get_result()


def get_user_entries_in_context(user_feed, start: datetime = None):
    user_entries = _get_and_create_user_entries(user_feed)

    batch_size = 25
    more = False

    if start:
        user_entries = user_entries.filter(
            entry__published__lt=start,
        )

    user_entries = user_entries.order_by("-entry__published")[:batch_size]
    if len(user_entries) == batch_size:
        more = True
        start = list(user_entries)[-1].entry.published

    context = {
        "user_feed": user_feed,
        "active_feed": user_feed,
        "user_entries": user_entries,
        "more_entries": more,
        "entries_start": start,
    }
    return context
