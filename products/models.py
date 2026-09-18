"""
Product model for BidKori marketplace.

Each product is owned by a seller (FK → User) and optionally enriched
with AI-generated metadata via the Gemini multimodal pipeline (Phase 2).
"""
import uuid
from django.conf import settings
from django.db import models


class Product(models.Model):
    """A listing item that can be attached to an auction."""

    class Condition(models.TextChoices):
        USED = 'USED', 'Used'
        REFURBISHED = 'REFURBISHED', 'Refurbished'
        LIKE_NEW = 'LIKE_NEW', 'Like New'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='products',
    )
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100)
    condition = models.CharField(max_length=50, choices=Condition.choices)
    description = models.TextField(blank=True, default='')
    image = models.ImageField(
        upload_to='products/%Y/%m/%d/',
        blank=True,
        null=True,
    )
    ai_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Gemini-generated structured metadata (overview, specs, etc.).',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'products_product'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_condition_display()})'
