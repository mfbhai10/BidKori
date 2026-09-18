"""
Auth URL routes — mounted at /api/auth/ in root urls.py.

Endpoints:
  POST /api/auth/register/       → RegisterView
  POST /api/auth/login/          → JWT TokenObtainPairView
  POST /api/auth/token/refresh/  → JWT TokenRefreshView
  GET  /api/auth/profile/        → UserProfileView
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, UserProfileView

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('profile/', UserProfileView.as_view(), name='profile'),
]
