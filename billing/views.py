"""
Billing API views — post-auction monetisation engine.

UnlockBuyerContactView   POST /api/auctions/<uuid>/unlock-buyer/
  Enforces Rule 4 (Masked Contact Protection): buyer delivery details
  remain hidden until the seller completes settlement. Settlement uses
  select_for_update() on SellerProfile inside transaction.atomic()
  to prevent race conditions (.antigravityrules Rule 1 pattern).

SubscribePremiumView     POST /api/seller/subscribe-premium/
  Mock/initialise a Premium GMV subscription for the authenticated seller.
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from auctions.models import Auction
from users.models import SellerProfile
from .models import Transaction
from .serializers import UnlockResponseSerializer

logger = logging.getLogger(__name__)

# Platform fee percentage for standard (non-premium) sellers
PLATFORM_FEE_RATE = Decimal('0.05')


class UnlockBuyerContactView(APIView):
    """
    POST /api/auctions/<uuid:auction_id>/unlock-buyer/

    Settlement flow that reveals masked buyer contact details.
    Strictly limited to the seller who owns the auctioned product.

    Atomic transaction with select_for_update() on SellerProfile
    prevents double-deduction or race conditions when two browser
    tabs trigger the unlock simultaneously.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, auction_id):
        # ── Fetch auction with related product + winner ──────
        try:
            auction = (
                Auction.objects
                .select_related('product', 'product__seller', 'winner')
                .get(id=auction_id)
            )
        except Auction.DoesNotExist:
            return Response(
                {'error': 'Auction not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Permission: only the product seller can unlock ───
        if auction.product.seller_id != request.user.id:
            return Response(
                {'error': 'Only the seller of this product can unlock buyer details.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Validate: auction must be in READY_TO_SHIP or SETTLEMENT ─
        allowed_statuses = (
            Auction.Status.READY_TO_SHIP,
            Auction.Status.SETTLEMENT,
        )
        if auction.status not in allowed_statuses:
            if auction.status in (Auction.Status.LIVE, Auction.Status.ENDED,
                                   Auction.Status.WINNER_VALIDATION):
                return Response(
                    {
                        'error': (
                            'Auction is still in progress or awaiting winner '
                            'validation. Contact unlock is not available yet.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if auction.status == Auction.Status.COMPLETED:
                # Already unlocked — return existing transaction data
                txn = Transaction.objects.filter(
                    auction=auction, is_unlocked=True,
                ).select_related('buyer').first()
                if txn:
                    return Response(
                        UnlockResponseSerializer({
                            'message': 'Buyer details already unlocked.',
                            'buyer_name': txn.buyer.full_name or txn.buyer.username,
                            'buyer_phone': txn.buyer.phone,
                            'buyer_email': txn.buyer.email,
                            'shipping_address': txn.buyer.shipping_address or 'Not provided yet',
                            'final_amount': txn.final_amount,
                            'platform_fee': txn.platform_fee,
                            'covered_by_subscription': txn.covered_by_subscription,
                            'transaction_id': txn.id,
                        }).data,
                        status=status.HTTP_200_OK,
                    )
            return Response(
                {'error': f'Auction status "{auction.get_status_display()}" does not allow contact unlock.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Validate: auction has a winner ───────────────────
        if not auction.winner:
            return Response(
                {'error': 'This auction has no winner. Cannot unlock buyer details.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Idempotency: already unlocked? ───────────────────
        existing_txn = Transaction.objects.filter(
            auction=auction, is_unlocked=True,
        ).select_related('buyer').first()
        if existing_txn:
            return Response(
                UnlockResponseSerializer({
                    'message': 'Buyer details already unlocked.',
                    'buyer_name': existing_txn.buyer.full_name or existing_txn.buyer.username,
                    'buyer_phone': existing_txn.buyer.phone,
                    'buyer_email': existing_txn.buyer.email,
                    'shipping_address': existing_txn.buyer.shipping_address or 'Not provided yet',
                    'final_amount': existing_txn.final_amount,
                    'platform_fee': existing_txn.platform_fee,
                    'covered_by_subscription': existing_txn.covered_by_subscription,
                    'transaction_id': existing_txn.id,
                }).data,
                status=status.HTTP_200_OK,
            )

        # ── Settlement Execution (Atomic) ────────────────────
        try:
            with transaction.atomic():
                # Lock SellerProfile to prevent concurrent GMV deductions
                seller_profile = (
                    SellerProfile.objects
                    .select_for_update()
                    .get(user=request.user)
                )

                final_amount = auction.current_bid

                # Path A — Premium GMV Subscriber
                if (
                    seller_profile.is_premium
                    and seller_profile.billing_cycle_end
                    and seller_profile.billing_cycle_end > timezone.now()
                    and (seller_profile.monthly_gmv_allowance - seller_profile.used_gmv) >= final_amount
                ):
                    seller_profile.used_gmv += final_amount
                    seller_profile.save(update_fields=['used_gmv'])
                    platform_fee = Decimal('0.00')
                    covered_by_subscription = True
                    logger.info(
                        f'Premium unlock: Seller {request.user.id} used ৳{final_amount} '
                        f'GMV allowance for auction {auction_id}'
                    )

                # Path B — Standard Pay-As-You-Sell
                else:
                    platform_fee = final_amount * PLATFORM_FEE_RATE
                    covered_by_subscription = False
                    logger.info(
                        f'Standard unlock: Seller {request.user.id} charged ৳{platform_fee} '
                        f'(5%) fee for auction {auction_id}'
                    )

                # Create Transaction record
                txn = Transaction.objects.create(
                    auction=auction,
                    buyer=auction.winner,
                    seller=request.user,
                    final_amount=final_amount,
                    platform_fee=platform_fee,
                    covered_by_subscription=covered_by_subscription,
                    is_unlocked=True,
                    payment_status=Transaction.PaymentStatus.COMPLETED,
                )

                # Transition auction → COMPLETED
                auction.status = Auction.Status.COMPLETED
                auction.save(update_fields=['status'])

        except SellerProfile.DoesNotExist:
            return Response(
                {'error': 'Seller profile not found. Please complete your seller setup.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Return unmasked buyer details ────────────────────
        buyer = auction.winner
        response_data = {
            'message': 'Buyer contact details unlocked successfully.',
            'buyer_name': buyer.full_name or buyer.username,
            'buyer_phone': buyer.phone,
            'buyer_email': buyer.email,
            'shipping_address': buyer.shipping_address or 'Not provided yet',
            'final_amount': txn.final_amount,
            'platform_fee': txn.platform_fee,
            'covered_by_subscription': txn.covered_by_subscription,
            'transaction_id': txn.id,
        }

        return Response(
            UnlockResponseSerializer(response_data).data,
            status=status.HTTP_200_OK,
        )


class SubscribePremiumView(APIView):
    """
    POST /api/seller/subscribe-premium/

    Mock endpoint to upgrade the authenticated seller to Premium GMV tier.
    Sets is_premium=True, monthly_gmv_allowance=200000.00, resets used_gmv,
    and sets billing_cycle_end to 30 days from now.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_seller:
            return Response(
                {'error': 'Only sellers can subscribe to Premium.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile, created = SellerProfile.objects.get_or_create(
            user=request.user,
        )

        profile.is_premium = True
        profile.monthly_gmv_allowance = Decimal('200000.00')
        profile.used_gmv = Decimal('0.00')
        profile.billing_cycle_end = timezone.now() + timedelta(days=30)
        profile.save(update_fields=[
            'is_premium', 'monthly_gmv_allowance',
            'used_gmv', 'billing_cycle_end',
        ])

        return Response(
            {
                'message': 'Premium subscription activated successfully.',
                'is_premium': True,
                'monthly_gmv_allowance': str(profile.monthly_gmv_allowance),
                'used_gmv': str(profile.used_gmv),
                'billing_cycle_end': profile.billing_cycle_end.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
