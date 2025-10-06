from django.template import loader

from rss_reader.api.entry_api import get_user_entries_in_context
from rss_reader.models import UserFeed


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
        return self

    def include_feeds(self):
        self._render_template("rss_reader/oob_feeds.html")
        return self

    def include_entries(self):
        self._render_template("rss_reader/oob_entries.html")
        return self

    def include_entry_content(self):
        # TODO: тут что-то не так
        self._render_template("rss_reader/entry.html")
        self._render_template("rss_reader/oob_entry_content.html")
        return self

    def include_add_feed_form(self):
        self._render_template("rss_reader/add_feed_form.html")
        return self

    def include_error_message(self):
        # TODO: ошибки часто никак не отображаются, может вынести их в модальное окно?
        self._render_template("rss_reader/error_message.html")
        return self

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
    renderer.include_entries()
    if add_form:
        renderer.include_add_feed_form()

    return renderer.get_result()


def render_all(request, user_entry):

    user_feeds = UserFeed.objects.filter(
        user=request.user,
    ).order_by("-pk")

    context = {
        "user_feeds": user_feeds,
        "user_entry": user_entry,
        "entry": user_entry.entry,
    }

    renderer = FeedsRenderer(request, context)
    renderer.include_feeds()
    renderer.include_entry_content()

    return renderer.get_result()


def render_entries(request, user_feed, start):
    # TODO: как-то выделять выбранный feed
    context = get_user_entries_in_context(user_feed, start)
    context.update(
        {
            "is_active": True,
        }
    )

    renderer = FeedsRenderer(request, context)
    renderer.include_entries()
    renderer.include_feed()

    return renderer.get_result()
