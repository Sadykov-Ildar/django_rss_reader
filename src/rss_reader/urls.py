from django.urls import path

from .views import entry_views
from .views import feed_views

app_name = "rss_reader"


urlpatterns = [
    path("feed/<int:feed_id>", feed_views.FeedView.as_view(), name="feed"),
    path("feed", feed_views.FeedView.as_view(), name="feed"),
    path("import_feeds", feed_views.import_feeds, name="import_feeds"),
    path(
        "entry_content/<int:entry_id>",
        entry_views.entry_content_view,
        name="entry_content",
    ),
    path("entries/<int:feed_id>", entry_views.entries_view, name="entries"),
]
