"""
Dashboard template views for sellers and buyers.

SellerDashboardView   GET /seller/dashboard/
  Displays sales analytics, GMV usage bar, and tabbed auction lists
  (Active/Scheduled, Ready to Ship with unlock CTA, Completed).

BuyerDashboardView    GET /buyer/dashboard/
  Displays active bids with rank, won auctions with delivery details,
  and watchlist placeholders.
"""
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Q
from django.views.generic import TemplateView

from auctions.models import Auction, Bid
from billing.models import Transaction
from users.models import SellerProfile


class SellerDashboardView(LoginRequiredMixin, TemplateView):
    """Seller dashboard — sales analytics + auction management."""
    template_name = 'billing/seller_dashboard.html'
    login_url = '/admin/login/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # ── Seller Profile & GMV Data ────────────────────────
        profile, _ = SellerProfile.objects.get_or_create(user=user)
        ctx['profile'] = profile

        # GMV progress percentage
        if profile.monthly_gmv_allowance > 0:
            ctx['gmv_percentage'] = min(
                round(float(profile.used_gmv / profile.monthly_gmv_allowance * 100), 1),
                100.0,
            )
        else:
            ctx['gmv_percentage'] = 0.0

        # ── Seller's Auctions ────────────────────────────────
        seller_auctions = (
            Auction.objects
            .filter(product__seller=user)
            .select_related('product', 'winner')
        )

        # Active & Scheduled
        ctx['active_auctions'] = list(
            seller_auctions.filter(
                status__in=[
                    Auction.Status.DRAFT,
                    Auction.Status.SCHEDULED,
                    Auction.Status.LIVE,
                ],
            ).order_by('-created_at')
        )

        # Ready to Ship (awaiting contact unlock)
        ctx['ready_auctions'] = list(
            seller_auctions.filter(
                status__in=[
                    Auction.Status.READY_TO_SHIP,
                    Auction.Status.SETTLEMENT,
                ],
            ).order_by('-created_at')
        )

        # Completed (unlocked)
        completed_auctions = list(
            seller_auctions.filter(
                status=Auction.Status.COMPLETED,
            ).order_by('-created_at')
        )
        ctx['completed_auctions'] = completed_auctions

        # Attach transaction data to completed auctions for buyer details
        for auction in completed_auctions:
            txn = (
                Transaction.objects
                .filter(auction=auction, is_unlocked=True)
                .select_related('buyer')
                .first()
            )
            auction.transaction = txn

        # ── Summary Cards ────────────────────────────────────
        seller_transactions = Transaction.objects.filter(seller=user)

        total_gmv = seller_transactions.filter(
            payment_status='COMPLETED',
        ).aggregate(total=Sum('final_amount'))['total'] or Decimal('0.00')
        ctx['total_gmv'] = total_gmv

        fees_saved = seller_transactions.filter(
            payment_status='COMPLETED',
            covered_by_subscription=True,
        ).aggregate(total=Sum('final_amount'))['total'] or Decimal('0.00')
        # Fees saved = what would have been 5% on subscription-covered sales
        ctx['fees_saved'] = fees_saved * Decimal('0.05')

        ctx['completed_count'] = seller_transactions.filter(
            payment_status='COMPLETED',
        ).count()

        return ctx


class BuyerDashboardView(LoginRequiredMixin, TemplateView):
    """Buyer dashboard — active bids, won auctions, watchlist."""
    template_name = 'billing/buyer_dashboard.html'
    login_url = '/admin/login/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # ── Active Bids ──────────────────────────────────────
        # Auctions where this buyer placed at least one bid and auction is live
        active_bid_auction_ids = (
            Bid.objects
            .filter(bidder=user, auction__status=Auction.Status.LIVE)
            .values_list('auction_id', flat=True)
            .distinct()
        )
        active_auctions = list(
            Auction.objects
            .filter(id__in=active_bid_auction_ids)
            .select_related('product', 'winner')
            .order_by('-created_at')
        )

        # Annotate each auction with this buyer's highest bid and rank
        for auction in active_auctions:
            my_top_bid = (
                Bid.objects
                .filter(auction=auction, bidder=user)
                .order_by('-amount')
                .first()
            )
            auction.my_bid_amount = my_top_bid.amount if my_top_bid else Decimal('0.00')
            auction.is_winning = (auction.winner_id == user.id)

        ctx['active_auctions'] = active_auctions

        # ── Won Auctions ─────────────────────────────────────
        won_auctions = list(
            Auction.objects
            .filter(
                winner=user,
                status__in=[
                    Auction.Status.READY_TO_SHIP,
                    Auction.Status.SETTLEMENT,
                    Auction.Status.COMPLETED,
                ],
            )
            .select_related('product', 'product__seller')
            .order_by('-created_at')
        )

        # Attach transaction data for each won auction
        for auction in won_auctions:
            txn = (
                Transaction.objects
                .filter(auction=auction, buyer=user)
                .first()
            )
            auction.transaction = txn

        ctx['won_auctions'] = won_auctions
        ctx['user'] = user

        # ── Watchlist (placeholder — bookmarking model not yet built) ──
        # For now, show recently bid-on auctions that are scheduled
        watchlist_auction_ids = (
            Bid.objects
            .filter(bidder=user)
            .exclude(auction__status=Auction.Status.LIVE)
            .values_list('auction_id', flat=True)
            .distinct()
        )
        ctx['watchlist_auctions'] = list(
            Auction.objects
            .filter(
                id__in=watchlist_auction_ids,
                status__in=[
                    Auction.Status.SCHEDULED,
                    Auction.Status.DRAFT,
                ],
            )
            .select_related('product')
            .order_by('-created_at')[:10]
        )

        return ctx
