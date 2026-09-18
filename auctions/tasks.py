"""
Celery Beat tasks for automated auction lifecycle transitions.

Runs every 5 seconds via CELERY_BEAT_SCHEDULE:
  SCHEDULED → LIVE   (when start_time ≤ now)
  LIVE → ENDED       (when end_time ≤ now)
    → READY_TO_SHIP  (bids exist & reserve met)
    → NO_WINNER      (no bids or reserve not met)

Broadcasts state changes to WebSocket groups so all connected
clients receive instant updates.
"""
import logging
from celery import shared_task
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


def _mask_email(email):
    """admin@gmail.com → a***@g***.com"""
    if not email or '@' not in email:
        return None
    local, domain = email.split('@', 1)
    m_local = local[0] + '***' if len(local) > 1 else '***'
    parts = domain.split('.')
    m_domain = parts[0][0] + '***' if len(parts[0]) > 1 else '***'
    return f'{m_local}@{m_domain}.{parts[-1]}'


@shared_task(name='auctions.tasks.transition_auction_states')
def transition_auction_states():
    """
    Periodic task — scans for auctions needing state transitions
    and broadcasts changes over WebSocket.
    """
    from auctions.models import Auction

    now = timezone.now()
    channel_layer = get_channel_layer()
    activated_count = 0
    ended_count = 0

    # ── SCHEDULED → LIVE ──────────────────────────────────
    scheduled = list(
        Auction.objects
        .filter(status=Auction.Status.SCHEDULED, start_time__lte=now)
        .select_related('product')
    )

    for auction in scheduled:
        auction.status = Auction.Status.LIVE
        auction.current_bid = auction.starting_bid
        auction.save(update_fields=['status', 'current_bid'])
        activated_count += 1

        logger.info(f'Auction {auction.id} → LIVE')

        try:
            async_to_sync(channel_layer.group_send)(
                f'auction_{auction.id}',
                {
                    'type': 'auction.lifecycle',
                    'data': {
                        'type': 'auction_started',
                        'auction_id': str(auction.id),
                        'product_title': auction.product.title,
                        'starting_bid': str(auction.starting_bid),
                        'start_time': auction.start_time.isoformat(),
                        'end_time': auction.end_time.isoformat(),
                        'server_time': now.isoformat(),
                    },
                },
            )
        except Exception as e:
            logger.warning(f'Broadcast failed for auction {auction.id}: {e}')

    # ── LIVE → ENDED ──────────────────────────────────────
    expired = list(
        Auction.objects
        .filter(status=Auction.Status.LIVE, end_time__lte=now)
        .select_related('product', 'winner')
    )

    for auction in expired:
        has_bids = auction.bids.exists()
        reserve_met = (
            auction.reserve_price is None
            or auction.current_bid >= auction.reserve_price
        )

        if has_bids and reserve_met:
            auction.status = Auction.Status.READY_TO_SHIP
        else:
            auction.status = Auction.Status.NO_WINNER
            auction.winner = None

        auction.save(update_fields=['status', 'winner'])
        ended_count += 1

        logger.info(f'Auction {auction.id} → {auction.status}')

        winner_display = (
            _mask_email(auction.winner.email)
            if auction.winner else None
        )

        try:
            async_to_sync(channel_layer.group_send)(
                f'auction_{auction.id}',
                {
                    'type': 'auction.lifecycle',
                    'data': {
                        'type': 'auction_ended',
                        'auction_id': str(auction.id),
                        'product_title': auction.product.title,
                        'final_status': auction.status,
                        'winner_display': winner_display,
                        'final_amount': str(auction.current_bid),
                        'server_time': now.isoformat(),
                    },
                },
            )
        except Exception as e:
            logger.warning(f'Broadcast failed for auction {auction.id}: {e}')

    if activated_count or ended_count:
        logger.info(
            f'Auction lifecycle: {activated_count} activated, '
            f'{ended_count} ended'
        )

    return {'activated': activated_count, 'ended': ended_count}
