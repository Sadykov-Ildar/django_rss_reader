import json

from channels.generic.websocket import AsyncWebsocketConsumer

from rss_reader.constants import WS_TASKS_REFRESHED_GROUP_NAME


class BackgroundTaskFinishNotifier(AsyncWebsocketConsumer):
    """
    Sends notification about finishing updates to all users at the same time,
    who then will reload page and DDoS our site :)

    Could be implemented better, but I am the only user, so it doesn't matter.
    """

    async def connect(self):
        self.group_name = WS_TASKS_REFRESHED_GROUP_NAME

        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def tasks_refreshed(self, event):
        message = event.get("message", "")

        # Send message to WebSocket
        await self.send(text_data=json.dumps({"message": message}))
