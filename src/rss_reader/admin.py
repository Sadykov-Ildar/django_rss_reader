# Register your models here.

from django.contrib import admin

from rss_reader.models import Feed, RequestHistory


class RequestHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "url",
        "status",
        "created_at",
    )
    search_fields = ("url", "status")
    fields = (
        "url",
        "status",
        "headers",
        "content",
        "created_at",
    )
    readonly_fields = ("created_at",)


class FeedAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "site_url",
        "last_updated",
        "updates_enabled",
        "update_after",
    )
    search_fields = ("title",)
    fields = (
        "title",
        "site_url",
        "rss_url",
        "last_updated",
        "updates_enabled",
        "update_after",
        "searched_image_url",
    )


admin.site.register(Feed, FeedAdmin)
admin.site.register(RequestHistory, RequestHistoryAdmin)
