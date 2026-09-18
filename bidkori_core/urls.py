"""
BidKori — Root URL Configuration.

API routes are namespaced under /api/.
Django Admin is at /admin/.
Seller-facing template views at /seller/.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from products.views import TaskStatusView, CreateListingView

# Customize admin site header
admin.site.site_header = 'BidKori Administration'
admin.site.site_title = 'BidKori Admin'
admin.site.index_title = 'Dashboard'

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # API — Auth
    path('api/auth/', include('users.urls')),

    # API — Products & AI
    path('api/products/', include('products.urls')),

    # API — Celery Task Polling
    path('api/tasks/<str:task_id>/status/', TaskStatusView.as_view(), name='task_status'),

    # Seller Template Views
    path('seller/create-listing/', CreateListingView.as_view(), name='create_listing'),

    # Auction Room
    path('auctions/', include('auctions.urls')),
]

# Serve media/static in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
