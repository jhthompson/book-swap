import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

from django.template.defaultfilters import date
from django.utils import timezone

from core.models import BookSwapMessage


class MessagesConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            self.close()
            return

        self.swap_id = self.scope["url_route"]["kwargs"]["id"]
        self.swap_group_name = f"swap_{self.swap_id}"

        # Join swap group
        async_to_sync(self.channel_layer.group_add)(
            self.swap_group_name, self.channel_name
        )

        self.accept()

    def disconnect(self, close_code):
        # Leave swap group
        async_to_sync(self.channel_layer.group_discard)(
            self.swap_group_name, self.channel_name
        )

    # Receive message from WebSocket
    def receive(self, text_data):
        # Validate user authentication on every message
        if not self.user.is_authenticated:
            self.close()
            return

        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Save message to database
        BookSwapMessage.objects.create(
            swap_id=self.swap_id,
            sender=self.user,
            content=message,
        )

        # Send message to swap group
        async_to_sync(self.channel_layer.group_send)(
            self.swap_group_name,
            {
                "type": "swap.message",
                "message": message,
                "user_id": self.user.id,
                "timestamp": date(timezone.now(), "N j, Y, P"),
            },
        )

    # Receive message from swap group
    def swap_message(self, event):
        message = event["message"]
        user_id = event["user_id"]
        timestamp = event["timestamp"]

        # Send message to WebSocket
        self.send(
            text_data=json.dumps(
                {
                    "message": message,
                    "user_id": user_id,
                    "timestamp": timestamp,
                }
            )
        )
