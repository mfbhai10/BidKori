"""
User and SellerProfile models for BidKori.

User inherits AbstractUser with UUID primary key, email-based login,
role-based access, and phone uniqueness.

SellerProfile is a 1-to-1 extension holding subscription & GMV data.
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user with role-based identity for BidKori marketplace."""

    class Role(models.TextChoices):
        BUYER = 'BUYER', 'Buyer'
        INDIVIDUAL_SELLER = 'INDIVIDUAL_SELLER', 'Individual Seller'
        BUSINESS_SELLER = 'BUSINESS_SELLER', 'Business Seller'
        ADMIN = 'ADMIN', 'Admin'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    email = models.EmailField(
        max_length=255,
        unique=True,
        help_text='Primary login identifier.',
    )
    phone = models.CharField(
        max_length=20,
        unique=True,
        help_text='Bangladeshi mobile number (e.g. +8801XXXXXXXXX).',
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.BUYER,
    )
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Use email as the login field instead of username
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'phone']

    class Meta:
        db_table = 'users_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.email} ({self.get_role_display()})'

    @property
    def is_seller(self):
        return self.role in (self.Role.INDIVIDUAL_SELLER, self.Role.BUSINESS_SELLER)


class SellerProfile(models.Model):
    """
    Extended profile for sellers.

    Tracks subscription tier (Premium vs Standard), monthly GMV allowance,
    and remaining quota for contact-unlock monetisation.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='seller_profile',
    )
    business_name = models.CharField(max_length=255, blank=True, null=True)
    trade_license_number = models.CharField(max_length=100, blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00)
    is_premium = models.BooleanField(
        default=False,
        help_text='Premium sellers pay via GMV allowance instead of per-transaction fees.',
    )
    monthly_gmv_allowance = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text='Total GMV (৳) allowed under Premium subscription this billing cycle.',
    )
    used_gmv = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text='GMV (৳) already consumed this billing cycle.',
    )
    billing_cycle_end = models.DateTimeField(
        blank=True, null=True,
        help_text='When the current Premium billing cycle expires.',
    )

    class Meta:
        db_table = 'users_seller_profile'
        verbose_name = 'Seller Profile'
        verbose_name_plural = 'Seller Profiles'

    def __str__(self):
        label = self.business_name or self.user.email
        return f'SellerProfile: {label}'

    @property
    def remaining_gmv(self):
        """GMV headroom remaining in the current billing cycle."""
        return self.monthly_gmv_allowance - self.used_gmv
