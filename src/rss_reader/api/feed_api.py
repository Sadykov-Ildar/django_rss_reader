from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from rss_reader.api.entry_api import _create_entries, get_user_entries
from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, UserEntry


@transaction.atomic
def create_feed_and_entries(user, rss_url: str, parsed_data: dict):
    """
    Create Feed and it's entries using parsed data.

    :raises URLValidationError:
    """
    feed_data: dict = parsed_data["feed"]
    image_url = feed_data.get("image_url")

    try:
        feed = Feed.objects.create(
            site_url=feed_data["link"],
            rss_url=rss_url,
            title=feed_data.get("title", ""),
            subtitle=feed_data.get("subtitle", ""),
            author=feed_data.get("author", ""),
            etag=parsed_data.get("etag") or "",
            modified=parsed_data.get("modified") or "",
            feed_type=parsed_data.get("feed_type", "rss"),
            image_url=image_url,
        )
    except IntegrityError as e:
        raise URLValidationError("Feed with this url already exists: " + str(e))
    _create_entries(feed, parsed_data)

    create_user_feed(feed, user)


def create_user_feed(feed: Feed, user):
    try:
        UserFeed.objects.create(user=user, feed=feed)
    except IntegrityError:
        raise URLValidationError("Feed with this url already exists.")


def get_user_feed_by_id(pk: int, user) -> UserFeed | None:
    try:
        return UserFeed.objects.select_related("feed").get(pk=pk, user=user)
    except UserFeed.DoesNotExist:
        return None


def get_user_feed_by_user_entry(user_entry: UserEntry, user) -> UserFeed | None:
    try:
        user_feed = UserFeed.objects.select_related("feed").get(
            feed=user_entry.entry.feed_id, user=user
        )
    except UserFeed.DoesNotExist:
        user_feed = None

    return user_feed


def get_ordered_user_feeds(user) -> QuerySet[UserFeed]:
    user_feeds = (
        UserFeed.objects.filter(
            user=user,
        )
        .select_related(
            "feed",
        )
        .order_by(
            "-pk",
        )
    )
    return user_feeds


def get_user_feeds(user) -> QuerySet[UserFeed]:
    return UserFeed.objects.filter(
        user=user,
    )


def delete_feed(feed: Feed):
    feed.delete()


@transaction.atomic
def delete_user_feed(user_feed: UserFeed):
    get_user_entries(
        user=user_feed.user_id,
    ).filter(
        entry__feed_id=user_feed.feed_id,
    ).delete()

    user_feed.delete()


@transaction.atomic
def delete_user_feeds_for_user(user):
    get_user_feeds(user).delete()

    get_user_entries(user=user).delete()
