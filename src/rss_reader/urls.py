from django.urls import path, register_converter

from . import url_converters
from .views import entry_views
from .views import feed_views
from .views import main_view

app_name = "rss_reader"

register_converter(url_converters.DateTimeConverter, "datetime")


urlpatterns = [
    path("feed/<int:user_feed_id>", feed_views.FeedView.as_view(), name="feed"),
    path("feed", feed_views.FeedView.as_view(), name="feed"),
    path("add_new_feed", feed_views.add_feed_modal, name="add_feed_modal"),
    path("import_feeds", feed_views.import_feeds, name="import_feeds"),
    path("refresh_feeds", feed_views.refresh_user_feeds, name="refresh_feeds"),
    path(
        "mark_feeds_as_read",
        feed_views.mark_feeds_as_read_view,
        name="mark_feeds_as_read",
    ),
    path(
        "mark_entries_as_read/<int:user_feed_id>",
        entry_views.mark_entries_as_read_view,
        name="mark_entries_as_read",
    ),
    path(
        "entry_content/<int:user_entry_id>",
        entry_views.entry_content_view,
        name="entry_content",
    ),
    path(
        "entries/<int:user_feed_id>/<datetime:start>",
        entry_views.entries_view,
        name="entries_pagination",
    ),
    path("entries/<int:user_feed_id>", entry_views.entries_view, name="entries"),
    path("settings", main_view.settings_view, name="settings"),
    path(
        "export_user_feeds", feed_views.export_user_feeds_view, name="export_user_feeds"
    ),
]
