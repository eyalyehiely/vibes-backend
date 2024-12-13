import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# Ensure settings module is defined before imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibes.settings')

# Import after the environment variable is set
django_asgi_app = get_asgi_application()

from authenticate.routing import websocket_urlpatterns  # Import after setting up Django application

application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Use the ASGI application created above
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})