"""
DRF serializers for user registration and profile retrieval.
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles new user sign-up.

    Accepts email, username, phone, role, and password with confirmation.
    Runs Django's built-in password validators.
    """
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'phone', 'password', 'password_confirm', 'role')

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError(
                {'password_confirm': 'Passwords do not match.'}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            phone=validated_data['phone'],
            password=validated_data['password'],
            role=validated_data.get('role', User.Role.BUYER),
        )


class UserSerializer(serializers.ModelSerializer):
    """Read-only user profile serializer (with writable delivery fields)."""

    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'phone', 'role',
            'is_verified', 'full_name', 'shipping_address', 'created_at',
        )
        read_only_fields = ('id', 'email', 'is_verified', 'created_at')

