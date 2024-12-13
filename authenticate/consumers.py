# from channels.generic.websocket import AsyncWebsocketConsumer
# from channels.db import database_sync_to_async
# from geopy.distance import geodesic
# import json
# import logging
# from rest_framework_simplejwt.tokens import AccessToken
# from django.contrib.auth.models import AnonymousUser
# from .models import CustomUser

# users_logger = logging.getLogger('users')

# class FriendSearchConsumer(AsyncWebsocketConsumer):
#     async def connect(self):
#         self.user = await self.get_user_from_token()
#         if self.user and not isinstance(self.user, AnonymousUser):
#             users_logger.info(f"User {self.user.username} connected to WebSocket.")
#             users_logger.debug(f"User latitude: {getattr(self.user, 'latitude', None)}, "
#                                f"longitude: {getattr(self.user, 'longitude', None)}")
#             await self.accept()
#         else:
#             users_logger.warning("Unauthenticated WebSocket connection attempt.")
#             await self.close(code=403)

#     @database_sync_to_async
#     def get_user_from_token(self):
#         """
#         Extracts the user from the provided token in the WebSocket query string.
#         """
#         query_string = self.scope['query_string'].decode()
#         users_logger.debug(f"WebSocket query string: {query_string}")
#         token_key = None
#         if "token=" in query_string:
#             token_key = query_string.split("token=")[-1]
#         if not token_key:
#             users_logger.error("No token provided in WebSocket query string.")
#             return AnonymousUser()
#         try:
#             access_token = AccessToken(token_key)
#             return CustomUser.objects.get(id=access_token['user_id'])
#         except Exception as e:
#             users_logger.error(f"Invalid token: {e}")
#             return AnonymousUser()

#     @database_sync_to_async
#     def get_active_users(self):
#         return CustomUser.objects.filter(search_friends=True).exclude(id=self.user.id)

#     async def disconnect(self, close_code):
#         users_logger.info(f"User {getattr(self, 'user', 'Unknown')} disconnected with code {close_code}.")

#     async def receive(self, text_data):
#         try:
#             data = json.loads(text_data)
#             radius = data.get('radius')

#             if not radius:
#                 await self.send(json.dumps({'error': 'Radius is required.'}))
#                 return

#             try:
#                 radius = float(radius)
#             except ValueError:
#                 await self.send(json.dumps({'error': 'Radius must be a valid number.'}))
#                 return

#             user_lat, user_lng = getattr(self.user, 'latitude', None), getattr(self.user, 'longitude', None)
#             if not user_lat or not user_lng:
#                 await self.send(json.dumps({'error': 'User location is not available.'}))
#                 return

#             active_users = await self.get_active_users()
#             friends_data = []

#             for friend in active_users:
#                 if friend.latitude and friend.longitude:
#                     distance = geodesic((user_lat, user_lng), (friend.latitude, friend.longitude)).kilometers
#                     if distance <= radius:
#                         friends_data.append({
#                             'id': friend.id,
#                             'first_name': friend.first_name,
#                             'last_name': friend.last_name,
#                             'latitude': friend.latitude,
#                             'longitude': friend.longitude,
#                             'distance': round(distance, 2),
#                         })

#             await self.send(json.dumps({'friends': friends_data}))
#         except Exception as e:
#             users_logger.error(f"Error in receive method: {e}")
#             await self.send(json.dumps({'error': 'An internal error occurred. Please try again later.'}))


from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from geopy.distance import geodesic
import json
import logging
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from .models import CustomUser

users_logger = logging.getLogger('users')

class FriendSearchConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = await self.get_user_from_token()
        if self.user and not isinstance(self.user, AnonymousUser):
            users_logger.info(f"User {self.user.username} connected to WebSocket.")
            users_logger.debug(f"User latitude: {getattr(self.user, 'latitude', None)}, "
                               f"longitude: {getattr(self.user, 'longitude', None)}")
            await self.accept()
        else:
            users_logger.warning("Unauthenticated WebSocket connection attempt.")
            await self.close(code=403)

    @database_sync_to_async
    def get_user_from_token(self):
        query_string = self.scope['query_string'].decode()
        users_logger.debug(f"WebSocket query string: {query_string}")
        token_key = None
        if "token=" in query_string:
            token_key = query_string.split("token=")[-1]
        if not token_key:
            users_logger.error("No token provided in WebSocket query string.")
            return AnonymousUser()
        try:
            access_token = AccessToken(token_key)
            user = CustomUser.objects.get(id=access_token['user_id'])
            users_logger.debug(f"User fetched: {user.username}, Latitude: {user.latitude}, Longitude: {user.longitude}")
            return user
        except Exception as e:
            users_logger.error(f"Invalid token or user fetch error: {e}")
            return AnonymousUser()

    @database_sync_to_async
    def fetch_active_users(self, user_id):
        """
        Fetch users who have `search_friends=True` excluding the current user.
        """
        return list(CustomUser.objects.filter(search_friends=True).exclude(id=user_id))

    async def disconnect(self, close_code):
        users_logger.info(f"User {getattr(self, 'user', 'Unknown')} disconnected with code {close_code}.")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            radius = data.get('radius')

            if not radius:
                await self.send(json.dumps({'error': 'Radius is required.'}))
                return

            try:
                radius = float(radius)
            except ValueError:
                await self.send(json.dumps({'error': 'Radius must be a valid number.'}))
                return

            user_lat, user_lng = getattr(self.user, 'latitude', None), getattr(self.user, 'longitude', None)
            if not user_lat or not user_lng:
                await self.send(json.dumps({'error': 'User location is not available.'}))
                return

            # Fetch active users asynchronously
            active_users = await self.fetch_active_users(self.user.id)
            friends_data = []

            for friend in active_users:
                if friend.latitude and friend.longitude:
                    distance = geodesic((user_lat, user_lng), (friend.latitude, friend.longitude)).kilometers
                    if distance <= radius:
                        friends_data.append({
                            'id': friend.id,
                            'first_name': friend.first_name,
                            'last_name': friend.last_name,
                            'latitude': friend.latitude,
                            'longitude': friend.longitude,
                            'distance': round(distance, 2),
                        })

            await self.send(json.dumps({'friends': friends_data}))
        except Exception as e:
            users_logger.error(f"Error in receive method: {e}")
            await self.send(json.dumps({'error': 'An internal error occurred. Please try again later.'}))