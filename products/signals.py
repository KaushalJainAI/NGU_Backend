# signals.py - Search KB updates + Cache invalidation
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import Product, ProductCombo, ProductSearchKB, ProductComboSearchKB, Category, ProductSection, ProductVariant
from .recommendations import SpiceSearchEngine
from .utils import run_in_background
from .cache import (
    invalidate_product_cache,
    invalidate_category_cache,
    invalidate_combo_cache,
    invalidate_search_cache,
    invalidate_by_prefix,
    CACHE_PREFIX_SECTIONS,
)

logger = logging.getLogger(__name__)
search_engine = SpiceSearchEngine()


# ============== PRODUCT SIGNALS ==============

@receiver(post_save, sender=Product)
def auto_update_product_on_save(sender, instance, created, **kwargs):
    """Update search KB and invalidate cache when product is saved."""
    # Update search KB asynchronously in background
    if instance.is_active and instance.stock > 0:
        run_in_background(search_engine.a_ensure_search_kb, instance)
    
    # Invalidate caches
    invalidate_product_cache()
    invalidate_search_cache()
    logger.info(f"Product cache invalidated for: {instance.name}")


@receiver(post_delete, sender=Product)
def invalidate_product_cache_on_delete(sender, instance, **kwargs):
    """Invalidate product and section caches when a product is deleted."""
    invalidate_product_cache()
    invalidate_search_cache()
    logger.info(f"Product cache invalidated (deleted): {instance.name}")


# ============== VARIANT SIGNALS ==============
# A variant carries the sellable price/stock for a product, so any change must
# bust the product list/section caches that embed variant data.

@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
def on_variant_change(sender, instance, **kwargs):
    # Keep the legacy Product fields in sync with the default variant so list
    # cards / cart fallbacks stay correct, then bust the caches.
    _mirror_default_variant_to_product(instance.product_id)
    invalidate_product_cache()
    invalidate_by_prefix(CACHE_PREFIX_SECTIONS)
    logger.info(f"Product cache invalidated (variant change): product {instance.product_id}")


def _mirror_default_variant_to_product(product_id):
    """Copy the product's default (or smallest active) variant's price/stock/
    weight onto the legacy Product fields. Uses .update() to avoid recursion."""
    default = (
        ProductVariant.objects.filter(product_id=product_id, is_default=True, is_active=True).first()
        or ProductVariant.objects.filter(product_id=product_id, is_active=True).order_by('weight').first()
    )
    if default is not None:
        Product.objects.filter(pk=product_id).update(
            price=default.price,
            discount_price=default.discount_price,
            weight=default.weight,
            unit=default.unit,
            stock=default.stock,
        )


# ============== COMBO SIGNALS ==============

@receiver(post_save, sender=ProductCombo)
def auto_update_combo_on_save(sender, instance, created, **kwargs):
    """Update search KB and invalidate cache when combo is saved."""
    # Update search KB asynchronously in background
    if instance.is_active:
        run_in_background(search_engine.a_ensure_search_kb, instance)
    
    # Invalidate caches
    invalidate_combo_cache()
    invalidate_search_cache()
    logger.info(f"Combo cache invalidated for: {instance.name}")


@receiver(post_delete, sender=ProductCombo)
def invalidate_combo_cache_on_delete(sender, instance, **kwargs):
    """Invalidate combo and section caches when a combo is deleted."""
    invalidate_combo_cache()
    invalidate_search_cache()
    logger.info(f"Combo cache invalidated (deleted): {instance.name}")


# ============== CATEGORY SIGNALS ==============

@receiver(post_save, sender=Category)
def refresh_category_on_save(sender, instance, **kwargs):
    """Refresh products and invalidate cache when category changes."""
    # Refresh product search KBs asynchronously in background
    for product in instance.products.filter(is_active=True):
        run_in_background(search_engine.a_ensure_search_kb, product)
    
    # Invalidate caches
    invalidate_category_cache()
    invalidate_product_cache()  # Products depend on categories
    invalidate_search_cache()
    logger.info(f"Category cache invalidated for: {instance.name}")


@receiver(post_delete, sender=Category)
def invalidate_category_cache_on_delete(sender, instance, **kwargs):
    """Invalidate category cache when a category is deleted."""
    invalidate_category_cache()
    invalidate_product_cache()
    logger.info(f"Category cache invalidated (deleted): {instance.name}")


# ============== SEARCH KB SIGNALS ==============
# Background LLM regeneration saves KB rows after the product/combo signals
# above have already fired — the corpus must invalidate when the KB lands.

@receiver(post_save, sender=ProductSearchKB)
@receiver(post_delete, sender=ProductSearchKB)
@receiver(post_save, sender=ProductComboSearchKB)
@receiver(post_delete, sender=ProductComboSearchKB)
def invalidate_search_cache_on_kb_change(sender, instance, **kwargs):
    invalidate_search_cache()


# ============== SECTION SIGNALS ==============

@receiver(post_save, sender=ProductSection)
def invalidate_section_cache_on_save(sender, instance, **kwargs):
    """Invalidate section cache when a section is saved."""
    invalidate_by_prefix(CACHE_PREFIX_SECTIONS)
    logger.info(f"Section cache invalidated for: {instance.name}")


@receiver(post_delete, sender=ProductSection)
def invalidate_section_cache_on_delete(sender, instance, **kwargs):
    """Invalidate section cache when a section is deleted."""
    invalidate_by_prefix(CACHE_PREFIX_SECTIONS)
    logger.info(f"Section cache invalidated (deleted): {instance.name}")
