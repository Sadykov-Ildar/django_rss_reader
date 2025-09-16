from django.urls import path

from rss_reader import views

app_name = "rss_reader"


urlpatterns = [
    path("", views.index, name="index"),
]
