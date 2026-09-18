from django.contrib import admin
from .models import Auction, Bid


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = (
        'short_id', 'product', 'status', 'starting_bid',
        'current_bid', 'start_time', 'end_time', 'winner',
    )
    list_filter = ('status', 'start_time', 'end_time')
    search_fields = ('product__title', 'winner__email', 'id')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Auction Identity', {
            'fields': ('id', 'product', 'status', 'winner'),
        }),
        ('Bid Configuration', {
            'fields': ('starting_bid', 'current_bid', 'bid_increment', 'reserve_price'),
        }),
        ('Schedule', {
            'fields': ('start_time', 'end_time', 'created_at'),
        }),
    )

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('short_id', 'auction', 'bidder', 'amount', 'ip_address', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('bidder__email', 'auction__product__title', 'ip_address')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

    @admin.display(description='ID')
    def short_id(self, obj):
        return str(obj.id)[:8]
