from django.urls import path

from core import consumers

websocket_urlpatterns = [
    path("ws/swap/<int:id>/messages", consumers.MessagesConsumer.as_asgi()),
]
