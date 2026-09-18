from django.contrib import admin
from .models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'short_id', 'auction', 'buyer', 'seller',
        'final_amount', 'platform_fee', 'covered_by_subscription',
        'is_unlocked', 'payment_status',
    )
    list_filter = ('payment_status', 'covered_by_subscription', 'is_unlocked')
    search_fields = ('buyer__email', 'seller__email', 'auction__product__title')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Parties', {
            'fields': ('id', 'auction', 'buyer', 'seller'),
        }),
        ('Financials', {
            'fields': ('final_amount', 'platform_fee', 'covered_by_subscription', 'payment_status'),
        }),
        ('Contact Unlock', {
            'fields': ('is_unlocked',),
        }),
        ('Timestamps', {
            'fields': ('created_at',),
        }),
    )

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]
