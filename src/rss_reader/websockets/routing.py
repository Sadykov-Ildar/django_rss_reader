from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(
        r"ws/background_tasks/$",
        consumers.BackgroundTaskFinishNotifier.as_asgi(),
    ),
]
