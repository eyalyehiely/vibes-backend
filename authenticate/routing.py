from django.urls import path
from .consumers import FriendSearchConsumer

websocket_urlpatterns = [
    path('ws/search-friends/', FriendSearchConsumer.as_asgi()),
]