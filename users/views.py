"""
Auth & profile API views.

- RegisterView   POST /api/auth/register/
- UserProfileView GET/PUT /api/auth/profile/
- JWT login & refresh are handled by simplejwt (see urls.py).
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, UserSerializer

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """Public endpoint for new user registration."""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'Registration successful.',
                'user': UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """Authenticated user can view/update their own profile."""
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
