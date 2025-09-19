from django.db import models


class Feed(models.Model):
    site_url = models.URLField(unique=True, verbose_name="Site URL")
    rss_url = models.URLField(max_length=255, verbose_name="RSS url")

    title = models.CharField()
    subtitle = models.CharField()
    author = models.CharField()

    etag = models.CharField()
    modified = models.DateTimeField(null=True)


class Entry(models.Model):
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    link = models.CharField()
    title = models.CharField()
    published = models.DateTimeField()
    author = models.CharField()
    content = models.TextField()
    summary = models.TextField()
