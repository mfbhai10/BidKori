"""
ASGI entrypoint for BidKori.

Configures ProtocolTypeRouter with HTTP (Django) and WebSocket (Channels).
WebSocket connections accept anonymous viewers and authenticate bidding clients
via Django session cookies or SimpleJWT tokens (query param, headers, or in-flight messages).
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bidkori_core.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from auctions.routing import websocket_urlpatterns  # noqa: E402
from auctions.middleware import JWTAuthMiddleware  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(
        JWTAuthMiddleware(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
