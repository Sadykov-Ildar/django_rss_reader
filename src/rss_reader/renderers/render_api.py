from datetime import datetime
from typing import Iterable

from django.conf import settings
from django.template import loader

from rss_reader.constants import ENTRIES_BATCH_SIZE
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rss_reader.models import UserFeed, UserEntry


class FeedsRenderer:
    """
    Class for building responses with partial templates to be rendered by HTMX.

    Usage:
        >>> renderer = FeedsRenderer(request, context)
        ... renderer.include_info_message()
        ... result = renderer.get_result()

    """

    def __init__(self, request, context=None, separator="\n\n"):
        self.request = request
        self.context = context or {}
        self._content = []
        self.separator = separator

    def get_result(self):
        return self.separator.join(self._content)

    def render_index(self):
        self._render_template("rss_reader/index.html")

    def include_oob_feed(self):
        self._render_template("rss_reader/feeds.html#oob_feed_partial")

    def include_oob_feeds(self):
        self._render_template("rss_reader/feeds.html#oob_feeds_partial")

    def include_entries(self):
        self._render_template("rss_reader/entries.html#entries_partial")

    def include_oob_entries(self):
        self._render_template("rss_reader/entries.html#oob_entries_partial")

    def include_entry(self):
        self._render_template("rss_reader/entries.html#entry_partial")

    def include_oob_entry_content(self):
        self._render_template("rss_reader/entry_content.html#oob_entry_content_partial")

    def include_add_feed_form(self):
        self._render_template("rss_reader/add_feed_form.html")

    def include_oob_entries_header(self):
        self._render_template(
            "rss_reader/entries_header.html#oob_entries_header_partial"
        )

    def include_oob_entry_content_header(self):
        self._render_template(
            "rss_reader/entry_content_header.html#oob_entry_content_header_partial"
        )

    def include_error_message(self):
        self._render_template("rss_reader/error_message.html")

    def include_info_message(self):
        self._render_template("rss_reader/info_message.html")

    def _render_template(self, template_name):
        if settings.DEBUG:
            self._content.append(f"<!-- {template_name} -->")
        self._content.append(
            loader.render_to_string(template_name, self.context, self.request)
        )


def render_main_page(
    request,
    user_feeds: Iterable[UserFeed],
    *,
    user_feed: UserFeed | None = None,
    user_entries: list[UserEntry],
    user_entry: UserEntry | None = None,
    start: datetime | None = None,
    search: str | None = None,
):
    context: dict = {
        "user_feeds": user_feeds,
    }
    if user_entry:
        context.update(
            {
                "active_entry": user_entry,
                "user_entry": user_entry,
                "entry": user_entry.entry,
            }
        )

    if user_feed:
        user_entries_context = get_user_entries_in_context(
            user_feed, user_entries, start, search
        )
        context.update(user_entries_context)

    renderer = FeedsRenderer(request, context)
    renderer.render_index()

    return renderer.get_result()


def render_info_message(request, info_message):
    context = {
        "info_message": info_message,
    }
    renderer = FeedsRenderer(request, context)
    renderer.include_info_message()

    return renderer.get_result()


def render_feeds_and_entries(
    request,
    user_feeds: Iterable[UserFeed],
    *,
    user_feed: UserFeed | None = None,
    user_entries: list[UserEntry],
    error_message="",
    add_form=False,
):
    context = {
        "user_feeds": user_feeds,
        "error_message": error_message,
    }

    if user_feed:
        context.update(get_user_entries_in_context(user_feed, user_entries))

    renderer = FeedsRenderer(request, context)
    renderer.include_oob_feeds()
    renderer.include_oob_entries_header()
    renderer.include_oob_entries()
    renderer.include_oob_entry_content()
    if add_form:
        renderer.include_add_feed_form()
    if error_message:
        renderer.include_error_message()

    return renderer.get_result()


def render_feed_and_entry(request, user_entry: UserEntry, user_feed: UserFeed):
    context = {
        "user_entry": user_entry,
        "user_feed": user_feed,
        "active_entry": user_entry,
        "active_feed": user_feed,
    }

    renderer = FeedsRenderer(request, context)
    renderer.include_entry()
    renderer.include_oob_feed()

    return renderer.get_result()


def render_entry_content(request, user_entry: UserEntry, user_feed: UserFeed):
    context = {
        "user_entry": user_entry,
        "entry": user_entry.entry,
        "active_entry": user_entry,
        "active_feed": user_feed,
        "user_feed": user_feed,
    }

    renderer = FeedsRenderer(request, context)
    renderer.include_oob_feed()
    renderer.include_entry()
    renderer.include_oob_entry_content()
    renderer.include_oob_entry_content_header()

    return renderer.get_result()


def render_entries(
    request,
    user_feed: UserFeed,
    user_entries: list[UserEntry],
    start: datetime | None = None,
    search: str | None = None,
):
    context = get_user_entries_in_context(user_feed, user_entries, start, search)

    renderer = FeedsRenderer(request, context)
    renderer.include_oob_feed()
    renderer.include_oob_entries_header()
    renderer.include_entries()
    renderer.include_oob_entry_content()
    renderer.include_oob_entry_content_header()

    return renderer.get_result()


def get_user_entries_in_context(
    user_feed: UserFeed,
    user_entries: list[UserEntry],
    start: datetime = None,
    search: str = None,
):
    more = False

    if len(user_entries) == ENTRIES_BATCH_SIZE:
        more = True
        start = list(user_entries)[-1].entry.published

    context = {
        "user_feed": user_feed,
        "active_feed": user_feed,
        "user_entries": user_entries,
        "more_entries": more,
        "entries_start": start,
        "search": search,
    }
    return context
