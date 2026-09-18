"""
Product API views and seller listing template view.

API Endpoints:
  POST   /api/products/create/                       → ProductCreateView
  POST   /api/products/<uuid>/generate-description/   → GenerateDescriptionView
  PATCH  /api/products/<uuid>/                        → ProductUpdateView
  POST   /api/products/<uuid>/publish-auction/        → PublishAuctionView
  GET    /api/tasks/<task_id>/status/                 → TaskStatusView

Template Views:
  GET    /seller/create-listing/                      → CreateListingView
"""
import logging
from django.shortcuts import get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from celery.result import AsyncResult
from django.utils import timezone

from .models import Product
from .serializers import (
    ProductCreateSerializer,
    ProductSerializer,
    ProductUpdateSerializer,
    AuctionPublishSerializer,
)
from .tasks import generate_ai_description_task
from auctions.models import Auction

logger = logging.getLogger(__name__)


# ── Template Views ────────────────────────────────────────────

class CreateListingView(LoginRequiredMixin, TemplateView):
    """Seller-facing listing creation wizard (Tailwind + Vanilla JS)."""
    template_name = 'products/create_listing.html'
    login_url = '/admin/login/'


# ── API Views ─────────────────────────────────────────────────

class ProductCreateView(generics.CreateAPIView):
    """
    POST /api/products/create/
    Multipart form data — creates a Product in draft state.
    """
    serializer_class = ProductCreateSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        return Response(
            ProductSerializer(product, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class GenerateDescriptionView(APIView):
    """
    POST /api/products/<uuid>/generate-description/
    Dispatches Celery AI task and returns task_id immediately.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, seller=request.user)
        extra_specs = request.data.get('extra_specs', '')
        task = generate_ai_description_task.delay(str(product.id), extra_specs)
        return Response({
            'task_id': task.id,
            'status': 'PENDING',
        })


class TaskStatusView(APIView):
    """
    GET /api/tasks/<task_id>/status/
    Polls Celery task status. Returns result payload on SUCCESS.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, task_id):
        result = AsyncResult(task_id)
        response_data = {
            'task_id': task_id,
            'status': result.status,
        }
        if result.ready():
            if result.successful():
                response_data['result'] = result.result
            else:
                response_data['error'] = str(result.result)
        return Response(response_data)


class ProductUpdateView(generics.UpdateAPIView):
    """
    PATCH /api/products/<uuid>/
    Allows seller to edit AI-generated or manual description before publishing.
    """
    serializer_class = ProductUpdateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Product.objects.filter(seller=self.request.user)


class PublishAuctionView(APIView):
    """
    POST /api/products/<uuid>/publish-auction/
    Creates an Auction record attached to the product.
    Sets status to LIVE if start_time ≤ now, otherwise SCHEDULED.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, seller=request.user)

        # Guard: one auction per product
        if hasattr(product, 'auction'):
            return Response(
                {'error': 'This product already has an auction.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AuctionPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Determine initial status
        now = timezone.now()
        auction_status = (
            Auction.Status.LIVE if data['start_time'] <= now
            else Auction.Status.SCHEDULED
        )

        auction = Auction.objects.create(
            product=product,
            starting_bid=data['starting_bid'],
            current_bid=data['starting_bid'],
            bid_increment=data['bid_increment'],
            reserve_price=data.get('reserve_price'),
            start_time=data['start_time'],
            end_time=data['end_time'],
            status=auction_status,
        )

        logger.info(
            f"Auction {auction.id} published for product {product.id} "
            f"as {auction.get_status_display()}"
        )

        return Response({
            'message': f'Auction published as {auction.get_status_display()}.',
            'auction_id': str(auction.id),
            'status': auction.status,
        }, status=status.HTTP_201_CREATED)
