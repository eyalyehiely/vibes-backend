from django.urls import path
from .consumers import *

websocket_urlpatterns = [
    path('ws/search-friends/', FriendSearchConsumer.as_asgi()),
    path('ws/chat/<str:room_id>/', ChatConsumer.as_asgi()),

]