"""
Auction URL routes — mounted at /auctions/ in root urls.py.

GET /auctions/<uuid:pk>/  → AuctionRoomView (live auction room template)
"""
from django.urls import path
from .views import AuctionRoomView

app_name = 'auctions'

urlpatterns = [
    path('<uuid:pk>/', AuctionRoomView.as_view(), name='auction_room'),
]
