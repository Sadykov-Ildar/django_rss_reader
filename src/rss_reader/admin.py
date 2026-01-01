# Register your models here.

from django.contrib import admin

from rss_reader.models import RequestHistory


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
    readonly_fields = (
        "created_at",
    )



admin.site.register(RequestHistory, RequestHistoryAdmin)
