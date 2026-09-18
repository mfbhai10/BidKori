from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'category', 'condition', 'created_at')
    list_filter = ('category', 'condition', 'created_at')
    search_fields = ('title', 'description', 'seller__email', 'category')
    readonly_fields = ('id', 'ai_metadata', 'created_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Listing Details', {
            'fields': ('id', 'seller', 'title', 'category', 'condition'),
        }),
        ('Content', {
            'fields': ('description', 'image', 'ai_metadata'),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )
