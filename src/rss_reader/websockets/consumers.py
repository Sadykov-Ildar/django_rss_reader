import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class BackgroundTaskFinishNotifier(WebsocketConsumer):
    def connect(self):
        self.group_name = "tasks_refreshed"

        async_to_sync(self.channel_layer.group_add)(self.group_name, self.channel_name)

        self.accept()

    def disconnect(self, close_code):
        async_to_sync(self.channel_layer.group_discard)(
            self.group_name, self.channel_name
        )

    def tasks_refreshed(self, event):
        message = event["message"]

        # Send message to WebSocket
        self.send(text_data=json.dumps({"message": message}))
