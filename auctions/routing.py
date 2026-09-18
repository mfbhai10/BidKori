"""
WebSocket URL routing for the auction bidding engine.
Imported by bidkori_core/asgi.py.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Auction live room: matches any valid or testing auction ID, with/without leading or trailing slash
    re_path(
        r'^/?ws/auctions/(?P<auction_id>[^/]+)/?$',
        consumers.AuctionBidConsumer.as_asgi(),
    ),
    # Fallback to prevent Daphne 500 ValueError crashes on unmatched paths
    re_path(
        r'^.*$',
        consumers.NotFoundConsumer.as_asgi(),
    ),
]
