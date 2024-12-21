
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from geopy.distance import geodesic
import json,logging,datetime
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
            if self.user.friends is None:
                self.user.friends = []

            for friend in active_users:
                if friend['latitude'] is not None and friend['longitude'] is not None:
                    distance = geodesic((user_lat, user_lng), (friend['latitude'], friend['longitude'])).kilometers
                    if distance <= radius:
                        friend['distance'] = round(distance, 2)
                        users_logger.debug(f"About to send email to {friend['username']} from user {self.user.username}")

                        # Wrap synchronous function in `sync_to_async`
                        await sync_to_async(send_friend_invitation_email)(friend['username'], self.user.first_name)
                        
                        # Check if the friend is already in the user's friends list
                        if not any(f['id'] == friend['id'] for f in self.user.friends):
                            # Append the friend's details if they are not already in the list
                            self.user.friends.append(
                                {
                                    'id': friend['id'],
                                    'first_name': friend['first_name'],
                                    'last_name': friend['last_name'],
                                    'username': friend['username'],
                                }
                            )
                            await sync_to_async(self.user.save)()  # Save the updated user object

                            users_logger.debug("Email sending function called.")
                            friends_data.append(friend)
                        else:
                            users_logger.debug(f"Friend {friend['id']} is already in the user's friends list.")

            # Send a list of friends email if applicable
            if len(friends_data) > 0:
                await sync_to_async(send_list_of_friends_email)(friends_data, self.user)

            users_logger.debug(f"Serialized friends data: {friends_data}")
            await self.send(json.dumps({'friends': friends_data}))

        except json.JSONDecodeError:
            users_logger.error("Invalid JSON format received.")
            await self.send(json.dumps({'error': 'Invalid JSON format.'}))
        except Exception as e:
            users_logger.error(f"Error in receive method: {e}")
            await self.send(json.dumps({'error': 'An internal error occurred. Please try again later.'}))



# --------------------------------------------chat app----------------------------------------------------------------


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'chat_message')
        
        if message_type == 'chat_message':
            message = data.get('message', '')
            sender_id = data.get('sender')
            receiver_id = data.get('receiver')
            
            # Save message to database
            await self.save_message(sender_id, receiver_id, message)

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': sender_id,
                    'receiver_id': receiver_id,
                    'timestamp': str(datetime.datetime.now())
                }
            )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message'],
            'sender_id': event['sender_id'],
            'receiver_id': event['receiver_id'],
            'timestamp': event['timestamp']
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, content):
        from authenticate.models import Message, ChatRoom
        
        chat_room = ChatRoom.objects.get(id=self.room_id)
        Message.objects.create(
            chat_room=chat_room,
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content
        )