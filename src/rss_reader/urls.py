from django.urls import path

from .views import entry_views
from .views import feed_views
from .views import main_view

app_name = "rss_reader"


urlpatterns = [
    path("feed/<int:feed_id>", feed_views.FeedView.as_view(), name="feed"),
    path("feed", feed_views.FeedView.as_view(), name="feed"),
    path(
        "entry_content/<int:entry_id>",
        entry_views.entry_content_view,
        name="entry_content",
    ),
    path("entries/<int:feed_id>", entry_views.entries_view, name="entries"),
    path("", main_view.index_view, name="index"),
]
