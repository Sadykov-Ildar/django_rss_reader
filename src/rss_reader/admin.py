# Register your models here.

from django.contrib import admin

from rss_reader.models import RequestHistory


class RequestHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "url",
        "status",
    )
    search_fields = ("url", "status")


admin.site.register(RequestHistory, RequestHistoryAdmin)
