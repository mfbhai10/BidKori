"""
Django Admin configuration for User and SellerProfile.

Provides inline SellerProfile editing within the User admin,
plus search/filter bars on key fields.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, SellerProfile


class SellerProfileInline(admin.StackedInline):
    """Inline editor for SellerProfile shown inside User detail."""
    model = SellerProfile
    can_delete = False
    verbose_name_plural = 'Seller Profile'
    fk_name = 'user'
    extra = 0
    fieldsets = (
        ('Business Info', {
            'fields': ('business_name', 'trade_license_number', 'rating'),
        }),
        ('Subscription & GMV', {
            'fields': ('is_premium', 'monthly_gmv_allowance', 'used_gmv', 'billing_cycle_end'),
        }),
    )


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [SellerProfileInline]
    list_display = ('email', 'phone', 'role', 'is_verified', 'is_active', 'created_at')
    list_filter = ('role', 'is_verified', 'is_active', 'is_staff')
    search_fields = ('email', 'phone', 'first_name', 'last_name', 'username')
    ordering = ('-created_at',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'username')}),
        ('Roles & Verification', {'fields': ('role', 'is_verified')}),
        ('Permissions', {
            'classes': ('collapse',),
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'phone', 'password1', 'password2', 'role'),
        }),
    )


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'business_name', 'rating', 'is_premium', 'monthly_gmv_allowance', 'used_gmv')
    list_filter = ('is_premium',)
    search_fields = ('user__email', 'business_name', 'trade_license_number')
    readonly_fields = ('id',)
