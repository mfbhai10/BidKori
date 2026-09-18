"""
DRF serializers for Product CRUD and Auction publishing.
"""
from rest_framework import serializers
from .models import Product
from auctions.models import Auction


class ProductCreateSerializer(serializers.ModelSerializer):
    """Handles multipart product creation (image + metadata)."""

    class Meta:
        model = Product
        fields = ('title', 'category', 'condition', 'image')

    def create(self, validated_data):
        validated_data['seller'] = self.context['request'].user
        return super().create(validated_data)


class ProductSerializer(serializers.ModelSerializer):
    """Full read serializer for product detail responses."""
    seller_email = serializers.EmailField(source='seller.email', read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'seller', 'seller_email', 'title', 'category',
            'condition', 'description', 'image', 'ai_metadata', 'created_at',
        )
        read_only_fields = ('id', 'seller', 'seller_email', 'ai_metadata', 'created_at')


class ProductUpdateSerializer(serializers.ModelSerializer):
    """Partial update — lets sellers edit AI-generated or manual description."""

    class Meta:
        model = Product
        fields = ('title', 'category', 'condition', 'description')


class AuctionPublishSerializer(serializers.Serializer):
    """Validates auction scheduling data before creating an Auction record."""
    starting_bid = serializers.DecimalField(max_digits=12, decimal_places=2)
    bid_increment = serializers.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True,
    )
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs['start_time'] >= attrs['end_time']:
            raise serializers.ValidationError(
                {'end_time': 'End time must be after start time.'}
            )
        rp = attrs.get('reserve_price')
        if rp is not None and rp < attrs['starting_bid']:
            raise serializers.ValidationError(
                {'reserve_price': 'Reserve price must be ≥ starting bid.'}
            )
        return attrs
