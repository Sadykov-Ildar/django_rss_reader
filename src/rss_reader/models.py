from django.contrib.auth import get_user_model
from django.db import models


class Feed(models.Model):
    site_url = models.URLField(max_length=255, verbose_name="Site URL")
    rss_url = models.URLField(unique=True, verbose_name="RSS url")
    # rss, atom, rdf
    feed_type = models.CharField(default="rss", max_length=10, verbose_name="Feed type")

    title = models.CharField()
    subtitle = models.CharField()
    author = models.CharField()

    etag = models.CharField()
    modified = models.CharField()

    image_url = models.URLField(max_length=255, null=True, blank=True)
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


class Entry(models.Model):
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
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    stale = models.BooleanField(default=True)

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
    url = models.URLField(db_index=True)

    headers = models.TextField()
    content = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Request history"
        db_table = "rss_reader_request_history"
