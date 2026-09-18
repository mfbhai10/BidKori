"""
DRF serializers for billing transactions and unlock responses.

TransactionSerializer — read-only view of a settlement record.
UnlockResponseSerializer — structures the unmasked buyer data returned
after a successful contact unlock.
"""
from rest_framework import serializers
from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    """Read-only serializer for billing transaction records."""

    buyer_email = serializers.EmailField(source='buyer.email', read_only=True)
    seller_email = serializers.EmailField(source='seller.email', read_only=True)
    auction_title = serializers.CharField(
        source='auction.product.title', read_only=True,
    )

    class Meta:
        model = Transaction
        fields = (
            'id', 'auction', 'auction_title',
            'buyer', 'buyer_email',
            'seller', 'seller_email',
            'final_amount', 'platform_fee',
            'covered_by_subscription', 'is_unlocked',
            'payment_status', 'created_at',
        )
        read_only_fields = fields


class UnlockResponseSerializer(serializers.Serializer):
    """
    Structures the unmasked buyer shipping data returned
    after the seller completes the contact-unlock settlement.
    """
    message = serializers.CharField()
    buyer_name = serializers.CharField()
    buyer_phone = serializers.CharField()
    buyer_email = serializers.EmailField()
    shipping_address = serializers.CharField()
    final_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    covered_by_subscription = serializers.BooleanField()
    transaction_id = serializers.UUIDField()
