"""
Auction views — template view for the live auction room.
"""
from django.views.generic import DetailView
from django.utils import timezone

from .models import Auction


class AuctionRoomView(DetailView):
    """
    Renders the live auction room page.
    WebSocket connection handles all real-time updates.
    """
    model = Auction
    template_name = 'auctions/auction_room.html'
    context_object_name = 'auction'

    def get_queryset(self):
        return (
            Auction.objects
            .select_related('product', 'product__seller', 'winner')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        auction = self.object
        ctx['bids'] = (
            auction.bids
            .select_related('bidder')
            .order_by('-created_at')[:20]
        )
        ctx['bid_count'] = auction.bids.count()
        ctx['is_seller'] = (
            self.request.user.is_authenticated
            and auction.product.seller_id == self.request.user.id
        )
        ctx['server_time'] = timezone.now().isoformat()
        return ctx
