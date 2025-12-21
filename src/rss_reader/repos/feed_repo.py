from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from django.db import IntegrityError, transaction
from django.db.models import QuerySet, Subquery, OuterRef, Q
from django.utils import timezone

from rss_reader.api._refresh_intervals import (
    get_update_delay_in_hours,
    should_slow_down,
    increase_update_interval,
    decrease_update_interval,
)
from rss_reader.constants import ENTRIES_BATCH_SIZE, HOURS_IN_YEAR
from rss_reader.helpers.html_cleaner import clean_html, resolve_urls

from rss_reader.exceptions import URLValidationError
from rss_reader.models import Feed, UserFeed, UserEntry, Entry
from vendoring.html_sanitizer.sanitizer import sanitize_html

if TYPE_CHECKING:
    from rss_reader.api.dtos import RequestResult
    from rss_reader.api.rss_parser import RssParsedData


class FeedRepo:
    @staticmethod
    def get_user_feed_by_id(pk: int, user) -> UserFeed | None:
        try:
            return UserFeed.objects.select_related("feed").get(pk=pk, user=user)
        except UserFeed.DoesNotExist:
            return None

    @staticmethod
    def get_user_feed_by_user_entry(user_entry: UserEntry, user) -> UserFeed | None:
        try:
            user_feed = UserFeed.objects.select_related("feed").get(
                feed=user_entry.entry.feed_id, user=user
            )
        except UserFeed.DoesNotExist:
            user_feed = None

        return user_feed

    @staticmethod
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

    @staticmethod
    def get_user_feeds(user) -> QuerySet[UserFeed]:
        return UserFeed.objects.filter(
            user=user,
        )

    @transaction.atomic
    def create_feed_and_entries(self, user, rss_data: RssParsedData):
        """
        Create Feed and it's entries using parsed data.

        :raises URLValidationError:
        """
        feed_data = rss_data.feed_data

        try:
            feed = Feed.objects.create(
                site_url=feed_data["site_url"],
                rss_url=feed_data["rss_url"],
                title=feed_data["title"],
                subtitle=feed_data["subtitle"],
                author=feed_data["author"],
                etag=feed_data["etag"],
                modified=feed_data["modified"],
                feed_type=feed_data["feed_type"],
                image_url=feed_data["image_url"],
            )
        except IntegrityError as e:
            raise URLValidationError("Feed with this url already exists: " + str(e))
        self.create_entries(feed, rss_data)

        self.create_user_feed(feed, user)

    def create_user_feed(self, feed: Feed, user):
        try:
            UserFeed.objects.create(user=user, feed=feed)
        except IntegrityError:
            raise URLValidationError("Feed with this url already exists.")

    def delete_feed(self, feed: Feed):
        feed.delete()

    @transaction.atomic
    def delete_user_feed(self, user_feed: UserFeed):
        self.get_user_entries(
            user=user_feed.user_id,  # ty: ignore
        ).filter(
            entry__feed_id=user_feed.feed_id,  # ty: ignore
        ).delete()

        user_feed.delete()

    @transaction.atomic
    def delete_user_feeds_for_user(self, user):
        self.get_user_feeds(user).delete()

        self.get_user_entries(user=user).delete()

    def _create_user_entries(self, user_id: int):
        """
        Creates UserEntry for every Entry, if UserEntry didn't exist before.
        """
        entries_with_user_entries = self.get_user_entries(
            user=user_id,
        ).values_list("entry_id", flat=True)
        entries = Entry.objects.exclude(
            id__in=entries_with_user_entries,
        )
        user_entries_bulk = [
            UserEntry(user_id=user_id, entry=entry) for entry in entries
        ]
        UserEntry.objects.bulk_create(user_entries_bulk, ignore_conflicts=True)

    def _get_and_create_user_entries(self, user_feed: UserFeed) -> QuerySet[UserEntry]:
        """
        Creates UserEntry if needed, and returns UserEntries for UserFeed

        :param user_feed:
        :return:
        """
        if user_feed.stale:
            self._create_user_entries(
                user_feed.user_id  # ty: ignore
            )
            user_feed.stale = False
            user_feed.save()

        user_entries = (
            self.get_user_entries(
                user_feed.user_id  # ty: ignore
            )
            .filter(
                entry__feed_id=user_feed.feed_id  # ty: ignore
            )
            .select_related("entry")
        )

        return user_entries

    def create_entries(self, feed: Feed, rss_data: RssParsedData):
        # update site_url in case it changed
        site_url = rss_data.feed_data["site_url"]
        if site_url and feed.site_url != site_url:
            feed.site_url = site_url

        entries_data = filter_parsed_data(rss_data, site_url)
        entry_bulk_create = []
        for record in reversed(entries_data):
            entry_bulk_create.append(
                Entry(
                    feed=feed,
                    link=record["link"],
                    title=record["title"],
                    published=record["published"],
                    author=record["author"],
                    content=record["content"],
                    summary=record["summary"],
                )
            )
        Entry.objects.bulk_create(entry_bulk_create, ignore_conflicts=True)

        feed.update_entry_count()
        feed.save()

    def mark_all_feeds_as_read(self, user):
        self.get_user_entries(user=user).update(read=True)

        # set read_count equal to feed.entry_count
        UserFeed.objects.filter(user_id=user).update(
            read_count=Subquery(
                UserFeed.objects.filter(pk=OuterRef("pk")).values("feed__entry_count")[
                    :1
                ]
            )
        )

    def mark_user_feed_as_read(self, user_feed: UserFeed):
        self.get_user_entries(
            user_feed.user_id  # ty: ignore
        ).filter(
            entry__feed=user_feed.feed_id,  # ty: ignore
        ).update(
            read=True,
        )
        user_feed.read_count = user_feed.feed.entry_count
        user_feed.save()

    def mark_entry_as_read(self, user_entry: UserEntry, user_feed):
        user_entry.read = True
        user_entry.save()

        user_feed.update_read_count()
        user_feed.save()

    def toggle_entry_read(self, user_entry: UserEntry, user_feed):
        user_entry.read = not user_entry.read
        user_entry.save()

        user_feed.update_read_count()
        user_feed.save()

    def get_user_entries(self, user) -> QuerySet[UserEntry]:
        return UserEntry.objects.filter(
            user_id=user,
        )

    def get_user_entry(self, user_entry_id: int, user) -> UserEntry | None:
        try:
            user_entry = (
                self.get_user_entries(
                    user=user,
                )
                .filter(
                    pk=user_entry_id,
                )
                .select_related("entry")
                .get()
            )
        except UserEntry.DoesNotExist:
            user_entry = None
        return user_entry

    def get_filtered_user_entries(
        self,
        user_feed: UserFeed,
        search: str | None = None,
        start: datetime | None = None,
    ) -> list[UserEntry]:
        user_entries = self._get_and_create_user_entries(user_feed)
        if search:
            user_entries = user_entries.filter(
                Q(entry__title__icontains=search)
                | Q(entry__content__icontains=search)
                | Q(entry__summary__icontains=search)
            )

        if start:
            user_entries = user_entries.filter(entry__published__lt=start)

        user_entries = user_entries.order_by("read", "-entry__published")
        user_entries = user_entries[:ENTRIES_BATCH_SIZE]

        return list(user_entries)

    def mark_user_feeds_as_stale(self, feed: Feed):
        UserFeed.objects.filter(feed=feed).update(stale=True)

    def get_feeds_for_refresh(self):
        return Feed.objects.filter(
            updates_enabled=True,
        ).filter(Q(update_after__isnull=True) | Q(update_after__lt=timezone.now()))

    def check_and_create_user_feed(self, rss_url: str, user) -> bool:
        """
        Validates URL, checks if feed for it already exists, creates UserFeed

        :param rss_url: RSS URL to check
        :param user: User
        :return: boolean flag, True if UserFeed was created, False otherwise
        :raises URLValidationError:
        """
        self._validate_rss_url(user, rss_url)
        try:
            feed = Feed.objects.get(rss_url=rss_url)
        except Feed.DoesNotExist:
            created = False
        else:
            self.create_user_feed(feed, user)
            created = True

        return created

    def _validate_rss_url(self, user, rss_url):
        """
        :raises URLValidationError:
        """
        if not rss_url:
            raise URLValidationError("Empty rss url")

        parsed_url = urlparse(rss_url)

        if not parsed_url.netloc:
            raise URLValidationError("Invalid URL")

        scheme = parsed_url.scheme
        if scheme not in ("http", "https"):
            raise URLValidationError("Url must start with http or https.")

        if self.get_user_feeds(user).filter(feed__rss_url=rss_url).exists():
            raise URLValidationError("Feed with this url already exists.")

    def get_feeds_with_unsearched_images(self) -> QuerySet[Feed, Feed]:
        return Feed.objects.filter(searched_image_url=False)

    @transaction.atomic
    def refresh_feed(
        self,
        feed: Feed,
        rss_data: RssParsedData,
        request_result: RequestResult,
    ):
        """
        Updates everything related to Feed and its Entries,
        also deals with redirects, update intervals.
        """
        current_time = timezone.now()

        feed.etag = rss_data.feed_data["etag"]
        feed.modified = rss_data.feed_data["modified"]

        feed.last_updated = current_time
        feed.last_exception = request_result.error_message

        feed.last_response_body = None
        if request_result.status not in {200, 304}:
            # response body could have hint that we need to show to user
            feed.last_response_body = request_result.content

        old_entry_count = feed.entry_count
        if rss_data.entries:
            self.mark_user_feeds_as_stale(feed)
            self.create_entries(feed, rss_data)
        # we need to check this now, because response could just have stale entries
        # or entries that we filtered out
        new_entries = feed.entry_count > old_entry_count

        self._change_feed_if_moved_or_disabled(feed, request_result)

        update_interval = _get_update_interval_in_hours(
            feed, new_entries, request_result
        )

        feed.update_interval = update_interval
        update_after = current_time + timedelta(hours=update_interval)
        update_after = update_after.replace(minute=0, second=0, microsecond=0)
        feed.update_after = update_after
        try:
            # transaction is necessary to create savepoint,
            # otherwise IntegrityError could roll back outer transaction
            with transaction.atomic():
                feed.save()
        except IntegrityError:
            # changing rss_url as a result of 301/308 permanent redirect can lead to merging two feeds into one
            self.delete_feed(feed)

    def _change_feed_if_moved_or_disabled(
        self, feed: Feed, request_result: RequestResult
    ):
        """
        Handles cases when Feed was moved temporarily or permanently, or stopped existing.
        """
        status = request_result.status
        headers = request_result.headers
        if status in {301, 308}:
            # moved permanently
            new_location = headers.get("Location")
            if new_location:
                feed.last_exception = f"Moved from {feed.rss_url} to {new_location}"
                feed.rss_url = new_location
        elif status in {302, 307}:
            new_location = headers.get("Location")
            if new_location:
                # moved temporarily
                feed.last_exception = (
                    f"Temporarily moved from {feed.rss_url} to {new_location}"
                )
            pass
        elif status == 410:
            # gone
            feed.updates_enabled = False
            feed.disabled_reason = 'Server responded with [status 410] "gone"'


def _get_update_interval_in_hours(
    feed: Feed, new_entries: bool, request_result: RequestResult
) -> int:
    update_interval = feed.update_interval
    update_delay = get_update_delay_in_hours(request_result.headers)
    if update_delay:
        update_interval = update_delay
    else:
        if should_slow_down(
            request_result.status, new_entries, request_result.error_message
        ):
            # slow down
            update_interval = increase_update_interval(update_interval)
        else:
            # new updates - speed up a little bit
            update_interval = decrease_update_interval(update_interval)

    if update_interval > HOURS_IN_YEAR:
        feed.updates_enabled = False
        feed.disabled_reason = "Last updated more than a year ago"
    if update_interval < 2:
        update_interval = 2
    return update_interval


def filter_parsed_data(rss_data: RssParsedData, site_url: str):
    result = []
    entries_data = rss_data.entries
    for entry in entries_data:
        link = entry["link"]
        if "youtube.com/shorts/" in link:  # YouTube shorts are bad
            continue
        content = entry["content"]
        summary = entry["summary"]

        if content:
            if content.startswith(summary[:100]):
                # summary is often the same as content - skip it
                summary = ""

            content = clean_html(content)
            content = resolve_urls(content, site_url)
            content = sanitize_html(content, "utf-8", "text/html")

        if summary:
            summary = clean_html(summary)
            summary = resolve_urls(summary, site_url)
            summary = sanitize_html(summary, "utf-8", "text/html")

        entry["content"] = content
        entry["summary"] = summary

        result.append(entry)

    return result
