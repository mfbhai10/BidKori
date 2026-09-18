"""
Transaction model for BidKori billing & monetisation.

Tracks post-auction settlement: platform fees, GMV subscription coverage,
and the contact-unlock gate that protects buyer delivery information.
"""
import uuid
from django.conf import settings
from django.db import models


class Transaction(models.Model):
    """
    Created when an auction reaches READY_TO_SHIP.

    The `is_unlocked` flag controls whether the seller can view
    the buyer's shipping details. Unlocking happens via either
    a 5% platform fee (Standard) or GMV allowance deduction (Premium).
    """

    class PaymentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        REFUNDED = 'REFUNDED', 'Refunded'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    auction = models.ForeignKey(
        'auctions.Auction',
        on_delete=models.CASCADE,
        related_name='transactions',
    )
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='purchases',
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sales',
    )
    final_amount = models.DecimalField(max_digits=12, decimal_places=2)
    platform_fee = models.DecimalField(max_digits=12, decimal_places=2)
    covered_by_subscription = models.BooleanField(
        default=False,
        help_text='True if the seller used Premium GMV allowance instead of paying a fee.',
    )
    is_unlocked = models.BooleanField(
        default=False,
        help_text='True once the seller has paid/used GMV to reveal buyer shipping details.',
    )
    payment_status = models.CharField(
        max_length=50,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'billing_transaction'
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f'Txn ৳{self.final_amount} — {self.get_payment_status_display()}'
