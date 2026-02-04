"""
URL configuration for django_rss_reader project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from rss_reader.views.main_view import index_view


def get_debug_toolbar_urls():
    if not settings.TESTING and settings.DEBUG:
        from debug_toolbar.toolbar import debug_toolbar_urls

        return debug_toolbar_urls()
    return []


urlpatterns = (
    [
        path("accounts/", include("accounts.urls")),
        path("admin/", admin.site.urls),
        path("rss_reader/", include("rss_reader.urls")),
        path("", index_view, name="index"),
    ]
    + get_debug_toolbar_urls()
    + static(
        settings.STATIC_URL,
    )
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
)
