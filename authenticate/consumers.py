
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from geopy.distance import geodesic
import json
import logging
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from .models import CustomUser
from .utils import send_friend_invitation_email,send_list_of_friends_email

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
        Fetch users who have `search_friends=True` excluding the current user,
        and return them as dictionaries of values.
        """
        qs = CustomUser.objects.filter(search_friends=True).exclude(id=user_id)
        users_list = list(qs.values('id', 'first_name', 'last_name','username', 'latitude', 'longitude'))

        # Convert UUID id to string for JSON serialization
        for user in users_list:
            user['id'] = str(user['id'])

        return users_list

    async def disconnect(self, close_code):
        users_logger.info(f"User {getattr(self, 'user', 'Unknown')} disconnected with code {close_code}.")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            users_logger.debug(f"Received data: {data}")
            radius = data.get('radius')

            if not radius:
                await self.send(json.dumps({'error': 'Radius is required.'}))
                return

            try:
                radius = float(radius)
            except ValueError:
                await self.send(json.dumps({'error': 'Radius must be a valid number.'}))
                return

            user_lat = self.user.latitude
            user_lng = self.user.longitude
            users_logger.info(f"User latitude: {user_lat}, longitude: {user_lng}")

            if user_lat is None or user_lng is None:
                await self.send(json.dumps({'error': 'User location is not available.'}))
                return

            # Fetch active users asynchronously
            active_users = await self.fetch_active_users(self.user.id)
            users_logger.debug(f"Active users fetched: {active_users}")
            friends_data = []

            for friend in active_users:
                if friend['latitude'] is not None and friend['longitude'] is not None:
                    distance = geodesic((user_lat, user_lng), (friend['latitude'], friend['longitude'])).kilometers
                    if distance <= radius:
                        friend['distance'] = round(distance, 2)
                        users_logger.debug(f"About to send email to {friend['username']} from user {self.user.username}")
                        send_friend_invitation_email(friend['username'], self.user.first_name)
                        users_logger.debug("Email sending function called.")
                        friends_data.append(friend)
            if len(friends_data)>0:
                send_list_of_friends_email(friends_data,self.user)

            users_logger.debug(f"Serialized friends data: {friends_data}")
            await self.send(json.dumps({'friends': friends_data}))
        except json.JSONDecodeError:
            users_logger.error("Invalid JSON format received.")
            await self.send(json.dumps({'error': 'Invalid JSON format.'}))
        except Exception as e:
            users_logger.error(f"Error in receive method: {e}")
            await self.send(json.dumps({'error': 'An internal error occurred. Please try again later.'}))