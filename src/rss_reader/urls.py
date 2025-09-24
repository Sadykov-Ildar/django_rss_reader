from django.urls import path

from .views import entry_views
from .views import feed_views

app_name = "rss_reader"


urlpatterns = [
    path("feed/<int:user_feed_id>", feed_views.FeedView.as_view(), name="feed"),
    path("feed", feed_views.FeedView.as_view(), name="feed"),
    path("import_feeds", feed_views.import_feeds, name="import_feeds"),
    path("refresh_feeds", feed_views.refresh_feeds, name="refresh_feeds"),
    path(
        "entry_content/<int:user_entry_id>",
        entry_views.entry_content_view,
        name="entry_content",
    ),
    path("entries/<int:user_feed_id>/<int:start>", entry_views.entries_view, name="entries_pagination"),
    path("entries/<int:user_feed_id>", entry_views.entries_view, name="entries"),
]
