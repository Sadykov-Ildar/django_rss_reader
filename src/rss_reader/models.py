from django.contrib.auth import get_user_model
from django.db import models

from rss_reader.helpers.date_helpers import get_delta_from_current_time_in_human


class Feed(models.Model):
    """
    Main model for RSS feed.
    All users who import the same RSS URL will have foreign key from UserFeed to the exact same Feed.
    """

    site_url = models.URLField(max_length=255, verbose_name="Site URL")
    rss_url = models.URLField(unique=True, verbose_name="RSS url")
    # rss, atom, rdf
    feed_type = models.CharField(default="rss", max_length=10, verbose_name="Feed type")

    title = models.CharField()
    subtitle = models.CharField()
    author = models.CharField()

    last_updated = models.DateTimeField(null=True, blank=True)
    # None if no errors
    last_exception = models.TextField(null=True, blank=True)
    # None if no errors
    last_response_body = models.TextField(null=True, blank=True)

    updates_enabled = models.BooleanField(default=True)
    disabled_reason = models.TextField(null=True, blank=True)
    update_interval = models.PositiveIntegerField(default=24)
    update_after = models.DateTimeField(null=True, blank=True)

    # etag and modified are needed to tell server that we already have entries up to a certain point in time,
    # allowing server to send only new data, which saves our resources when parsing new entries
    etag = models.CharField()
    modified = models.CharField()

    image_url = models.URLField(max_length=255, null=True, blank=True)
    image = models.FileField(
        "img", max_length=500, upload_to="favicons/", null=True, blank=True
    )
    # have we already tried searching for image URL or not
    searched_image_url = models.BooleanField(default=False)

    entry_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "Feeds"
        db_table = "rss_reader_feeds"

        indexes = [
            models.Index(
                fields=["searched_image_url"],
                condition=models.Q(searched_image_url=False),
                name="partial_searched_image_url",
            ),
        ]

    def update_entry_count(self):
        self.entry_count = Entry.objects.filter(
            feed=self.pk,
        ).count()

    @property
    def last_updated_delta_from_current_time(self):
        return get_delta_from_current_time_in_human(self.last_updated)

    @property
    def update_after_delta_from_current_time(self):
        return get_delta_from_current_time_in_human(self.update_after)


class Entry(models.Model):
    """
    Entry in RSS feed.
    """

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    link = models.CharField()
    title = models.CharField()
    published = models.DateTimeField(db_index=True)
    author = models.CharField()
    content = models.TextField()
    summary = models.TextField()

    class Meta:
        ordering = ["-published"]
        verbose_name_plural = "Entries"
        db_table = "rss_reader_entries"

        unique_together = ("feed", "link")


class UserFeed(models.Model):
    """
    Exists to keep track of Feeds that user wants to read.
    """

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    # True if there are new entries that don't have corresponding UserEntry for this user, False otherwise.
    # Exists to avoid creating UserEntry for inactive users
    stale = models.BooleanField(default=True)

    # Amount of UserEntry that was read by user
    read_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name_plural = "User feeds"
        db_table = "rss_reader_user_feeds"

        unique_together = ("user", "feed")

    def update_read_count(self):
        self.read_count = UserEntry.objects.filter(
            user=self.user_id,
            entry__feed=self.feed_id,
            read=True,
        ).count()

    @property
    def unread_count(self):
        return self.feed.entry_count - self.read_count


class UserEntry(models.Model):
    """
    Exists to keep track of entries that was read by user.

    Created on demand, when user actually opens RSS reader.
    """

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)

    read = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "User entries"
        db_table = "rss_reader_user_entries"

        unique_together = ("user", "entry")

        indexes = [
            models.Index(
                fields=["user", "read"],
                condition=models.Q(read=True),
                name="user_entry_partial_read",
            ),
        ]


class RequestHistory(models.Model):
    """
    History of requests to refresh Feed.
    """

    url = models.URLField(db_index=True)

    status = models.PositiveIntegerField()
    headers = models.TextField()
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Request history"
        db_table = "rss_reader_request_history"
