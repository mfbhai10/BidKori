"""
Celery tasks for AI-powered product description generation.

Uses Google Gemini (gemini-2.5-flash) multimodal model to analyse
product images and generate structured listing descriptions.

Per .antigravityrules Rule 3: All AI API interactions run exclusively
inside Celery tasks — never blocking HTTP/WebSocket request-response cycles.
"""
import os
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def generate_ai_description_task(self, product_id, extra_specs=""):
    """
    Generate a structured AI description for a product listing.

    Args:
        product_id: UUID string of the Product to process.
        extra_specs: Optional additional specifications from the seller.

    Returns:
        dict with product_id, status, and generated description.
    """
    from products.models import Product

    try:
        product = Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        logger.error(f"Product {product_id} not found.")
        return {"product_id": product_id, "status": "FAILED", "error": "Product not found."}

    try:
        from google import genai
        from PIL import Image

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key == "your-gemini-api-key":
            raise ValueError("GEMINI_API_KEY is not configured. Set it in your .env file.")

        client = genai.Client(api_key=api_key)

        # ── Build Prompt ──────────────────────────────────────
        prompt = (
            "You are an expert product listing specialist for BidKori, "
            "a premium online auction marketplace in Bangladesh.\n\n"
            "Analyze the provided product image and generate a detailed, "
            "professional product description in structured markdown.\n\n"
            f"Product Title: {product.title}\n"
            f"Category: {product.category}\n"
            f"Listed Condition: {product.get_condition_display()}\n"
        )
        if extra_specs:
            prompt += f"Additional Specifications from Seller: {extra_specs}\n"

        prompt += (
            "\nGenerate the description in EXACTLY this structure:\n\n"
            "## Overview\n"
            "Write a compelling 2-3 sentence overview highlighting the product's key value.\n\n"
            "## Physical Condition Assessment\n"
            "Based on your visual inspection of the image, describe the physical "
            "condition honestly — note any visible scratches, wear, dents, discoloration, "
            "or signs of use. If the item appears to be in good condition, note that.\n\n"
            "## Technical Highlights & Specifications\n"
            "- List key technical specifications based on what you can identify\n"
            "- Include notable features and capabilities\n"
            "- Mention any visible accessories or included items\n"
            "- Note the brand and model if identifiable\n\n"
            "Keep the tone professional, honest, and engaging. Write in English.\n"
            "Do NOT include any preamble or closing remarks outside the structure above."
        )

        # ── Build Content Parts ───────────────────────────────
        contents = [prompt]

        if product.image:
            try:
                img = Image.open(product.image.path)
                contents.append(img)
                logger.info(f"Image loaded for product {product_id}: {product.image.path}")
            except Exception as img_err:
                logger.warning(f"Could not load image for product {product_id}: {img_err}")

        # ── Call Gemini API ───────────────────────────────────
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
        )

        generated_text = response.text

        # ── Persist Results ───────────────────────────────────
        product.description = generated_text
        product.ai_metadata = {
            "model": "gemini-2.5-flash",
            "status": "SUCCESS",
            "generated_at": timezone.now().isoformat(),
            "extra_specs": extra_specs,
            "char_count": len(generated_text),
        }
        product.save(update_fields=["description", "ai_metadata"])

        logger.info(
            f"AI description generated for product {product_id} "
            f"({len(generated_text)} chars)."
        )

        return {
            "product_id": str(product.id),
            "status": "SUCCESS",
            "description": generated_text,
        }

    except Exception as exc:
        logger.error(f"AI generation failed for product {product_id}: {exc}")

        # Mark failure in metadata
        product.ai_metadata = {
            "status": "FAILED",
            "error": str(exc),
            "failed_at": timezone.now().isoformat(),
        }
        product.save(update_fields=["ai_metadata"])

        # Retry on transient errors
        raise self.retry(exc=exc)
