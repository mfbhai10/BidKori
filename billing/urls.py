"""
Billing API URL routes — mounted at /api/ in root urls.py.

Endpoints:
  POST /api/auctions/<uuid:auction_id>/unlock-buyer/ → UnlockBuyerContactView
  POST /api/seller/subscribe-premium/                → SubscribePremiumView
"""
from django.urls import path
from .views import UnlockBuyerContactView, SubscribePremiumView

app_name = 'billing'

urlpatterns = [
    path(
        'auctions/<uuid:auction_id>/unlock-buyer/',
        UnlockBuyerContactView.as_view(),
        name='unlock_buyer',
    ),
    path(
        'seller/subscribe-premium/',
        SubscribePremiumView.as_view(),
        name='subscribe_premium',
    ),
]
