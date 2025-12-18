from django.db.models import QuerySet
from django.utils import timezone
from opml import OpmlDocument

from rss_reader.models import UserFeed


def get_feeds_in_opml(user_feeds: QuerySet[UserFeed]) -> str:
    """
    Prepares string that contains OPML document with RSS urls that can be imported into
    another RSS reader.
    """
    document = OpmlDocument(
        title="Django RSS Reader Subscriptions",
        date_created=timezone.now(),
    )
    for user_feed in user_feeds:
        feed = user_feed.feed
        document.add_outline(
            title=feed.title,
            text=feed.title,
            description=feed.subtitle,
            type=feed.feed_type,
            xml_url=feed.rss_url,
            html_url=feed.site_url,
        )
    file_content = str(document)

    return str(file_content)
