"""
Auction and Bid models for BidKori real-time bidding engine.

Auction uses a 10-state finite state machine (see PROJECT_BLUEPRINT.md §4.1).
Bid records every individual bid with anti-fraud metadata (IP, user-agent).
"""
import uuid
from django.conf import settings
from django.db import models


class Auction(models.Model):
    """
    A live auction tied 1-to-1 to a Product.

    The `status` field drives the entire auction lifecycle from DRAFT
    through to COMPLETED / CANCELLED / NO_WINNER.
    """

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SCHEDULED = 'SCHEDULED', 'Scheduled'
        LIVE = 'LIVE', 'Live'
        ENDED = 'ENDED', 'Ended'
        WINNER_VALIDATION = 'WINNER_VALIDATION', 'Winner Validation'
        READY_TO_SHIP = 'READY_TO_SHIP', 'Ready to Ship'
        SETTLEMENT = 'SETTLEMENT', 'Settlement'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'
        NO_WINNER = 'NO_WINNER', 'No Winner'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    product = models.OneToOneField(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='auction',
    )
    starting_bid = models.DecimalField(max_digits=12, decimal_places=2)
    current_bid = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    bid_increment = models.DecimalField(max_digits=12, decimal_places=2)
    reserve_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        blank=True, null=True,
        help_text='Minimum price the seller will accept. Hidden from bidders.',
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_auctions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auctions_auction'
        verbose_name = 'Auction'
        verbose_name_plural = 'Auctions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_time'], name='idx_auction_status_start'),
            models.Index(fields=['status', 'end_time'], name='idx_auction_status_end'),
        ]

    def __str__(self):
        return f'Auction: {self.product.title} [{self.get_status_display()}]'

    @property
    def is_live(self):
        return self.status == self.Status.LIVE


class Bid(models.Model):
    """
    An individual bid placed during a live auction.

    Stores IP address and user-agent for anti-shill-bidding
    heuristics (Phase 5 governance).
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    auction = models.ForeignKey(
        Auction,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    bidder = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bids',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auctions_bid'
        verbose_name = 'Bid'
        verbose_name_plural = 'Bids'
        ordering = ['-amount']
        indexes = [
            models.Index(fields=['auction', '-amount'], name='idx_bid_auction_amount'),
        ]

    def __str__(self):
        return f'Bid ৳{self.amount} on {self.auction_id} by {self.bidder.email}'
