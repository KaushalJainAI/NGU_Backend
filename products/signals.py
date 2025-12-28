# signals.py - Search KB updates + Cache invalidation
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

from .models import Product, ProductCombo, ProductSearchKB, ProductComboSearchKB, Category, ProductSection
from .recommendations import SpiceSearchEngine
from .cache import (
    invalidate_product_cache,
    invalidate_category_cache,
    invalidate_combo_cache,
    invalidate_by_prefix,
    CACHE_PREFIX_SECTIONS,
)

logger = logging.getLogger(__name__)
search_engine = SpiceSearchEngine()


# ============== PRODUCT SIGNALS ==============

@receiver(post_save, sender=Product)
def auto_update_product_on_save(sender, instance, created, **kwargs):
    """Update search KB and invalidate cache when product is saved."""
    # Update search KB
    if instance.is_active and instance.stock > 0:
        search_engine.ensure_search_kb(instance)
    
    # Invalidate caches
    invalidate_product_cache()
    logger.info(f"Product cache invalidated for: {instance.name}")


@receiver(post_delete, sender=Product)
def invalidate_product_cache_on_delete(sender, instance, **kwargs):
    """Invalidate product and section caches when a product is deleted."""
    invalidate_product_cache()
    logger.info(f"Product cache invalidated (deleted): {instance.name}")


# ============== COMBO SIGNALS ==============

@receiver(post_save, sender=ProductCombo)
def auto_update_combo_on_save(sender, instance, created, **kwargs):
    """Update search KB and invalidate cache when combo is saved."""
    # Update search KB
    if instance.is_active:
        search_engine.ensure_search_kb(instance)
    
    # Invalidate caches
    invalidate_combo_cache()
    logger.info(f"Combo cache invalidated for: {instance.name}")


@receiver(post_delete, sender=ProductCombo)
def invalidate_combo_cache_on_delete(sender, instance, **kwargs):
    """Invalidate combo and section caches when a combo is deleted."""
    invalidate_combo_cache()
    logger.info(f"Combo cache invalidated (deleted): {instance.name}")


# ============== CATEGORY SIGNALS ==============

@receiver(post_save, sender=Category)
def refresh_category_on_save(sender, instance, **kwargs):
    """Refresh products and invalidate cache when category changes."""
    # Refresh product search KBs
    for product in instance.products.filter(is_active=True):
        search_engine.ensure_search_kb(product)
    
    # Invalidate caches
    invalidate_category_cache()
    invalidate_product_cache()  # Products depend on categories
    logger.info(f"Category cache invalidated for: {instance.name}")


@receiver(post_delete, sender=Category)
def invalidate_category_cache_on_delete(sender, instance, **kwargs):
    """Invalidate category cache when a category is deleted."""
    invalidate_category_cache()
    invalidate_product_cache()
    logger.info(f"Category cache invalidated (deleted): {instance.name}")


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
