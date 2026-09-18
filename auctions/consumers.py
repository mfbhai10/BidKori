"""
WebSocket consumer for real-time auction bidding.

Per .antigravityrules Rules 1 & 2:
  - Every bid uses select_for_update() inside transaction.atomic()
  - All countdowns, winner determination, and bid eligibility are server-authoritative
  - Frontend NEVER calculates these values

Groups:
  auction_{id}  → all viewers of a specific auction
  user_{id}     → private channel for targeted OUTBID alerts
"""
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Auction, Bid
from .middleware import get_user_from_jwt

logger = logging.getLogger(__name__)



class AuctionBidConsumer(AsyncJsonWebsocketConsumer):

    # ── Connection Lifecycle ───────────────────────────────

    async def connect(self):
        self.auction_id = self.scope['url_route']['kwargs']['auction_id']
        self.auction_group = f'auction_{self.auction_id}'
        self.user = self.scope.get('user')
        self.is_authenticated = bool(self.user and self.user.is_authenticated)

        # Join auction broadcast group
        await self.channel_layer.group_add(self.auction_group, self.channel_name)

        # Authenticated users also join their private channel
        if self.is_authenticated:
            self.user_group = f'user_{self.user.id}'
            await self.channel_layer.group_add(self.user_group, self.channel_name)

        await self.accept()

        # Push full auction state on connect (clock-sync included)
        initial = await self._get_initial_state()
        await self.send_json(initial)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.auction_group, self.channel_name)
        if self.is_authenticated:
            await self.channel_layer.group_discard(
                f'user_{self.user.id}', self.channel_name,
            )

    # ── Inbound Message Router ─────────────────────────────

    async def receive_json(self, content):
        msg_type = content.get('type')

        if msg_type == 'place_bid':
            await self._handle_place_bid(content)
        elif msg_type == 'authenticate':
            await self._handle_authenticate(content)
        elif msg_type == 'ping':
            await self.send_json({
                'type': 'pong',
                'server_time': timezone.now().isoformat(),
            })

    async def _handle_authenticate(self, content):
        token = content.get('token')
        if not token:
            await self.send_json({
                'type': 'auth_error',
                'error': 'Missing token in authentication request.',
            })
            return

        user = await get_user_from_jwt(token)
        if user:
            self.user = user
            self.is_authenticated = True
            self.user_group = f'user_{self.user.id}'
            await self.channel_layer.group_add(self.user_group, self.channel_name)
            await self.send_json({
                'type': 'authenticated',
                'user_id': str(user.id),
                'email': self._mask_email(user.email),
                'message': 'Successfully authenticated.',
            })
        else:
            await self.send_json({
                'type': 'auth_error',
                'error': 'Invalid or expired token.',
            })

    # ── Bid Handler ────────────────────────────────────────

    async def _handle_place_bid(self, content):
        # Support in-line token authentication if client passed a token
        if not self.is_authenticated and content.get('token'):
            user = await get_user_from_jwt(content['token'])
            if user:
                self.user = user
                self.is_authenticated = True
                self.user_group = f'user_{self.user.id}'
                await self.channel_layer.group_add(self.user_group, self.channel_name)

        if not self.is_authenticated:
            await self.send_json({
                'type': 'bid_rejected',
                'error': 'You must be logged in to place bids.',
            })
            return


        try:
            amount = Decimal(str(content.get('amount', 0)))
        except (InvalidOperation, TypeError, ValueError):
            await self.send_json({
                'type': 'bid_rejected',
                'error': 'Invalid bid amount.',
            })
            return

        # Extract client metadata for anti-fraud tracking
        headers = dict(self.scope.get('headers', []))
        ip = self._get_client_ip(headers)
        ua = headers.get(b'user-agent', b'').decode('utf-8', errors='replace')[:500]

        result = await self._process_bid_atomic(amount, ip, ua)

        if result['success']:
            # Confirm to the bidder
            await self.send_json({
                'type': 'bid_accepted',
                'bid_id': result['bid_id'],
                'amount': str(result['amount']),
            })

            # Broadcast NEW_HIGHEST_BID to the auction room
            await self.channel_layer.group_send(
                self.auction_group,
                {
                    'type': 'auction.new_bid',
                    'amount': str(result['amount']),
                    'bidder_display': result['bidder_display'],
                    'bid_count': result['bid_count'],
                    'end_time': result['end_time'],
                    'server_time': result['server_time'],
                    'anti_snipe_extended': result['anti_snipe_extended'],
                },
            )

            # Send targeted OUTBID alert to previous highest bidder
            prev = result.get('prev_bidder_id')
            if prev and prev != str(self.user.id):
                await self.channel_layer.group_send(
                    f'user_{prev}',
                    {
                        'type': 'auction.outbid',
                        'auction_id': str(self.auction_id),
                        'new_amount': str(result['amount']),
                        'your_last_bid': str(result['prev_bid_amount']),
                        'product_title': result['product_title'],
                    },
                )
        else:
            await self.send_json({
                'type': 'bid_rejected',
                'error': result['error'],
            })

    # ── Group Message Handlers ─────────────────────────────
    #    (called by channel_layer.group_send)

    async def auction_new_bid(self, event):
        """Broadcast: a new highest bid was placed."""
        await self.send_json({
            'type': 'new_highest_bid',
            'amount': event['amount'],
            'bidder_display': event['bidder_display'],
            'bid_count': event['bid_count'],
            'end_time': event['end_time'],
            'server_time': event['server_time'],
            'anti_snipe_extended': event['anti_snipe_extended'],
        })

    async def auction_outbid(self, event):
        """Private: you have been outbid."""
        await self.send_json({
            'type': 'outbid',
            'auction_id': event['auction_id'],
            'new_amount': event['new_amount'],
            'your_last_bid': event['your_last_bid'],
            'product_title': event['product_title'],
        })

    async def auction_lifecycle(self, event):
        """Broadcast from Celery Beat: auction started / ended."""
        await self.send_json(event['data'])

    # ── Atomic Database Operations ─────────────────────────

    @database_sync_to_async
    def _get_initial_state(self):
        try:
            auction = (
                Auction.objects
                .select_related('product', 'product__seller', 'winner')
                .get(id=self.auction_id)
            )
        except (Auction.DoesNotExist, ValidationError, ValueError):
            return {
                'type': 'error',
                'error': f'Auction "{self.auction_id}" not found.',
                'server_time': timezone.now().isoformat(),
            }
        except Exception as exc:
            logger.error(f'Error retrieving initial auction state: {exc}', exc_info=True)
            return {
                'type': 'error',
                'error': 'Could not load auction details.',
                'server_time': timezone.now().isoformat(),
            }

        recent_bids = list(
            Bid.objects.filter(auction=auction)
            .select_related('bidder')
            .order_by('-created_at')[:20]
        )

        is_seller = (
            self.is_authenticated
            and str(auction.product.seller_id) == str(self.user.id)
        )

        return {
            'type': 'connection_established',
            'auction_id': str(auction.id),
            'product_title': auction.product.title,
            'product_image': auction.product.image.url if auction.product.image else None,
            'product_condition': auction.product.get_condition_display(),
            'product_category': auction.product.category,
            'seller_display': self._mask_email(auction.product.seller.email),
            'status': auction.status,
            'current_bid': str(auction.current_bid),
            'starting_bid': str(auction.starting_bid),
            'bid_increment': str(auction.bid_increment),
            'bid_count': auction.bids.count(),
            'start_time': auction.start_time.isoformat(),
            'end_time': auction.end_time.isoformat(),
            'server_time': timezone.now().isoformat(),
            'winner_display': (
                self._mask_email(auction.winner.email)
                if auction.winner else None
            ),
            'recent_bids': [
                {
                    'amount': str(b.amount),
                    'bidder_display': self._mask_email(b.bidder.email),
                    'created_at': b.created_at.isoformat(),
                }
                for b in recent_bids
            ],
            'is_authenticated': self.is_authenticated,
            'is_seller': is_seller,
        }

    @database_sync_to_async
    def _process_bid_atomic(self, amount, ip_address, user_agent):
        """
        Core bid processing with strict ACID guarantees.

        Acquires an exclusive row lock via select_for_update() before
        any validation — bid eligibility is NEVER computed without
        holding the lock (.antigravityrules Rule 1).
        """
        try:
            with transaction.atomic():
                # ── Lock the auction row ──────────────────
                auction = (
                    Auction.objects
                    .select_for_update(of=('self',))
                    .select_related('product')
                    .get(id=self.auction_id)
                )


                # ── Validate: auction is LIVE ─────────────
                if auction.status != Auction.Status.LIVE:
                    return {
                        'success': False,
                        'error': f'Auction is not live (status: {auction.get_status_display()}).',
                    }

                # ── Validate: shill bidding guard ─────────
                if str(auction.product.seller_id) == str(self.user.id):
                    return {
                        'success': False,
                        'error': 'Sellers cannot bid on their own listings.',
                    }

                # ── Validate: minimum bid amount ──────────
                min_bid = auction.current_bid + auction.bid_increment
                if amount < min_bid:
                    return {
                        'success': False,
                        'error': f'Bid must be at least ৳{min_bid:,.2f}.',
                    }

                # ── Capture previous highest bidder ───────
                prev_bidder_id = (
                    str(auction.winner_id) if auction.winner_id else None
                )
                prev_bid_amount = auction.current_bid

                # ── Anti-sniping: extend if < 30s left ────
                now = timezone.now()
                remaining = (auction.end_time - now).total_seconds()
                anti_snipe = False
                if remaining < 30:
                    auction.end_time += timedelta(seconds=60)
                    anti_snipe = True

                # ── Persist Bid record ────────────────────
                bid = Bid.objects.create(
                    auction=auction,
                    bidder=self.user,
                    amount=amount,
                    ip_address=ip_address or '0.0.0.0',
                    user_agent=user_agent,
                )

                # ── Update auction state ──────────────────
                auction.current_bid = amount
                auction.winner = self.user
                auction.save(update_fields=['current_bid', 'winner', 'end_time'])

                bid_count = auction.bids.count()

                return {
                    'success': True,
                    'bid_id': str(bid.id),
                    'amount': amount,
                    'bidder_display': self._mask_email(self.user.email),
                    'bid_count': bid_count,
                    'end_time': auction.end_time.isoformat(),
                    'server_time': timezone.now().isoformat(),
                    'anti_snipe_extended': anti_snipe,
                    'prev_bidder_id': prev_bidder_id,
                    'prev_bid_amount': prev_bid_amount,
                    'product_title': auction.product.title,
                }

        except (Auction.DoesNotExist, ValidationError, ValueError):
            return {'success': False, 'error': 'Auction not found.'}
        except Exception as exc:
            logger.error(f'Bid processing error: {exc}', exc_info=True)
            return {'success': False, 'error': 'An unexpected error occurred.'}

    # ── Helpers ────────────────────────────────────────────

    def _get_client_ip(self, headers):
        xff = headers.get(b'x-forwarded-for', b'').decode()
        if xff:
            return xff.split(',')[0].strip()
        client = self.scope.get('client')
        return client[0] if client else '0.0.0.0'

    @staticmethod
    def _mask_email(email):
        """admin@gmail.com → a***@g***.com"""
        if not email or '@' not in email:
            return '***'
        local, domain = email.split('@', 1)
        m_local = local[0] + '***' if len(local) > 1 else '***'
        parts = domain.split('.')
        m_domain = parts[0][0] + '***' if len(parts[0]) > 1 else '***'
        return f'{m_local}@{m_domain}.{parts[-1]}'


class NotFoundConsumer(AsyncJsonWebsocketConsumer):
    """
    Fallback consumer to prevent Daphne/Channels from throwing unhandled
    ValueError: No route found for path exceptions on invalid WebSocket paths.
    """

    async def connect(self):
        await self.accept()
        await self.send_json({
            'type': 'error',
            'error': 'Endpoint not found.',
            'server_time': timezone.now().isoformat(),
        })
        await self.close(code=4004)

