"""
JWT & Session Authentication Middleware for Django Channels.

Allows:
1. Anonymous viewers: scope['user'] is AnonymousUser.
   Allowed to view live auctions and receive real-time broadcasts.
2. Session-authenticated users: scope['user'] resolved via Django sessions
   (handled by AuthMiddlewareStack).
3. JWT-authenticated users (bidding clients & API integrations):
   - Extracted from query string: ?token=<jwt> or ?jwt=<jwt>
   - Or extracted from 'authorization' header: Bearer <jwt>
   - Or extracted from Sec-WebSocket-Protocol: bearer.<jwt>
   - Validated via SimpleJWT AccessToken
"""
import logging
import urllib.parse
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_jwt(token_str):
    """Resolve active User instance from a SimpleJWT access token string."""
    if not token_str:
        return None
    try:
        token = AccessToken(token_str)
        user_id = token.get('user_id')
        if not user_id:
            return None
        return User.objects.filter(id=user_id, is_active=True).first()
    except (TokenError, Exception) as exc:
        logger.debug(f'JWT WebSocket authentication failed: {exc}')
        return None


class JWTAuthMiddleware(BaseMiddleware):
    """
    ASGI middleware that parses and validates SimpleJWT tokens for WebSockets.
    Preserves existing session authentication and gracefully falls back to
    AnonymousUser without dropping the connection.
    """

    async def __call__(self, scope, receive, send):
        # If user is already authenticated via session cookie, keep it
        user = scope.get('user')
        if not user or isinstance(user, AnonymousUser) or not getattr(user, 'is_authenticated', False):
            token = None

            # 1. Inspect query string: ?token=<jwt> or ?jwt=<jwt>
            query_string = scope.get('query_string', b'').decode('utf-8', errors='ignore')
            if query_string:
                params = urllib.parse.parse_qs(query_string)
                token_param = params.get('token') or params.get('jwt')
                if token_param:
                    token = token_param[0]

            # 2. Inspect headers for Authorization: Bearer <jwt>
            if not token and 'headers' in scope:
                headers = dict(scope.get('headers', []))
                auth_header = headers.get(b'authorization', b'').decode('utf-8', errors='ignore')
                if auth_header.lower().startswith('bearer '):
                    token = auth_header.split(' ', 1)[1].strip()

            # 3. Inspect Sec-WebSocket-Protocol header
            if not token and 'headers' in scope:
                headers = dict(scope.get('headers', []))
                protocols = headers.get(b'sec-websocket-protocol', b'').decode('utf-8', errors='ignore')
                for p in protocols.split(','):
                    p = p.strip()
                    if p.lower().startswith('bearer.'):
                        token = p.split('.', 1)[1].strip()
                        break

            # If token found, attempt resolution
            if token:
                resolved_user = await get_user_from_jwt(token)
                if resolved_user:
                    scope['user'] = resolved_user

        # Ensure scope['user'] is at minimum AnonymousUser
        if 'user' not in scope or scope['user'] is None:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
