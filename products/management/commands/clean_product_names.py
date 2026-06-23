"""
One-time data fix: strip trailing weight tokens (e.g. "500g", "1 kg", "(250g)")
from product/combo names so the stored name is the display name.

This replaces the runtime stripping the frontend used to do in
formatProductName(). The weight is already stored separately on the
weight/unit fields, so removing it from the name loses no information.

Covers:
  - Product.name
  - ProductCombo.name        (unique — collisions are skipped, not forced)
  - OrderItem.product_name    (historical snapshots, so old orders stay clean)

It removes BOTH the leading brand name ("Nidhi" / "Nidhi Masala" /
"Nidhi Grah Udyog") and the trailing weight token. Safe to run repeatedly
(idempotent). Defaults to a dry run; pass --apply to write.

    python manage.py clean_product_names            # preview
    python manage.py clean_product_names --apply     # commit
"""
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from products.models import Product, ProductCombo
from orders.models import OrderItem

# Trailing weight token. Mirrors the frontend WEIGHT_SUFFIX regex in
# src/lib/utils.ts so behavior is identical to what users currently see.
WEIGHT_SUFFIX = re.compile(
    r'[\s(\-]*\d+(?:\.\d+)?\s*(?:g|gm|gms|kg|ml|l|ltr)\.?\)?\s*$',
    re.IGNORECASE,
)

# Leading brand name to drop from titles. Longest variants first so
# "Nidhi Grah Udyog" is matched before bare "Nidhi". Edit this list if the
# brand wording in your data differs.
BRAND_PREFIX = re.compile(
    r'^\s*nidhi(?:\s+(?:masala|grah\s+udyog))?\b[\s\-:]*',
    re.IGNORECASE,
)


def strip_brand(name: str) -> str:
    """Drop a leading brand name; never return an empty string."""
    if not name:
        return name
    stripped = BRAND_PREFIX.sub('', name.strip()).strip()
    return stripped or name.strip()


def strip_weight(name: str) -> str:
    """Repeatedly trim a trailing weight token; never return an empty string."""
    if not name:
        return name
    cleaned = name.strip()
    while True:
        stripped = WEIGHT_SUFFIX.sub('', cleaned).strip()
        if stripped == cleaned or not stripped:
            break
        cleaned = stripped
    return cleaned or name.strip()


def clean_name(name: str) -> str:
    """Strip the leading brand and the trailing weight from a product title."""
    return strip_weight(strip_brand(name))


class Command(BaseCommand):
    help = "Strip trailing weight tokens from product/combo/order-item names in the DB."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist changes. Without this flag the command only previews (dry run).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        mode = 'APPLY' if apply else 'DRY RUN'
        self.stdout.write(self.style.WARNING(f"clean_product_names — {mode}\n"))

        with transaction.atomic():
            p_changed = self._clean_products(apply)
            c_changed = self._clean_combos(apply)
            o_changed = self._clean_order_items(apply)

            if not apply:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Products: {p_changed} | Combos: {c_changed} | Order items: {o_changed} "
            f"{'updated' if apply else 'would change'}."
        ))
        if not apply:
            self.stdout.write(self.style.WARNING("Dry run — nothing was saved. Re-run with --apply to commit."))

    def _clean_products(self, apply):
        changed = 0
        for product in Product.objects.all().only('id', 'name'):
            new_name = clean_name(product.name)
            if new_name != product.name:
                changed += 1
                self.stdout.write(f"  [product {product.id}] {product.name!r} -> {new_name!r}")
                if apply:
                    Product.objects.filter(pk=product.pk).update(name=new_name)
        return changed

    def _clean_combos(self, apply):
        changed = 0
        existing = set(ProductCombo.objects.values_list('name', flat=True))
        for combo in ProductCombo.objects.all().only('id', 'name'):
            new_name = clean_name(combo.name)
            if new_name == combo.name:
                continue
            # name is unique — don't collide with a different existing combo.
            if new_name in existing and new_name != combo.name:
                self.stdout.write(self.style.WARNING(
                    f"  [combo {combo.id}] SKIP {combo.name!r} -> {new_name!r} (name already taken)"
                ))
                continue
            changed += 1
            self.stdout.write(f"  [combo {combo.id}] {combo.name!r} -> {new_name!r}")
            if apply:
                ProductCombo.objects.filter(pk=combo.pk).update(name=new_name)
                existing.discard(combo.name)
                existing.add(new_name)
        return changed

    def _clean_order_items(self, apply):
        changed = 0
        for item in OrderItem.objects.all().only('id', 'product_name'):
            new_name = clean_name(item.product_name)
            if new_name != item.product_name:
                changed += 1
                if apply:
                    OrderItem.objects.filter(pk=item.pk).update(product_name=new_name)
        # Order items are numerous; summarize rather than list each.
        self.stdout.write(f"  [order items] {changed} snapshot name(s) {'updated' if apply else 'to change'}")
        return changed
