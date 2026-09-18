"""
Product API URL routes — mounted at /api/products/ in root urls.py.

Endpoints:
  POST   /api/products/create/                        → ProductCreateView
  POST   /api/products/<uuid:pk>/generate-description/ → GenerateDescriptionView
  PATCH  /api/products/<uuid:pk>/                     → ProductUpdateView
  POST   /api/products/<uuid:pk>/publish-auction/     → PublishAuctionView
"""
from django.urls import path
from .views import (
    ProductCreateView,
    GenerateDescriptionView,
    ProductUpdateView,
    PublishAuctionView,
)

app_name = 'products'

urlpatterns = [
    path('create/', ProductCreateView.as_view(), name='product_create'),
    path(
        '<uuid:pk>/generate-description/',
        GenerateDescriptionView.as_view(),
        name='generate_description',
    ),
    path('<uuid:pk>/', ProductUpdateView.as_view(), name='product_update'),
    path(
        '<uuid:pk>/publish-auction/',
        PublishAuctionView.as_view(),
        name='publish_auction',
    ),
]
