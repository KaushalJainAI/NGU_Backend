"""
Regression tests for the e-commerce resilience gaps G1, G2 (deterministic).

G1 — a delisted (is_active=False) product/combo must not be orderable from a
     stale cart.
G2 — a combo's availability is bounded by its COMPONENT stock, ordering a combo
     decrements component inventory, and cancelling restores it.
"""
from decimal import Decimal

import pytest

from conftest import create_test_image
from products.models import Product, ProductCombo, ProductComboItem
from cart.models import Cart, CartItem
from orders.models import Order

URL = "/api/orders/"
ADDR = {"shipping_address": "1 Rd", "phone_number": "1234567890", "payment_method": "COD"}


def _product(cat, name, price="100.00", stock=5):
    return Product.objects.create(
        name=name, category=cat, description="x", price=Decimal(price), stock=stock,
        weight=Decimal("250.00"), unit="g", spice_form="powder", is_active=True,
        image=create_test_image(f"{name}.jpg"),
    )


def _combo(name, *components):
    combo = ProductCombo.objects.create(name=name, price=Decimal("300.00"), is_active=True)
    for product, qty in components:
        ProductComboItem.objects.create(combo=combo, product=product, quantity=qty)
    return combo


# --------------------------------------------------------------------------- #
# G1
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestInactiveNotOrderable:
    def test_inactive_product_blocked(self, authenticated_client, test_user, test_category):
        p = _product(test_category, "Delisted", stock=5)
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, product=p, item_type="product", quantity=1)
        Product.objects.filter(pk=p.pk).update(is_active=False)
        r = authenticated_client.post(URL, ADDR, format="json")
        assert r.status_code == 400
        assert "no longer available" in r.json().get("error", "").lower()
        assert not Order.objects.filter(user=test_user).exists()

    def test_inactive_combo_blocked(self, authenticated_client, test_user, test_category):
        a = _product(test_category, "CompA", stock=5)
        combo = _combo("Delisted Combo", (a, 1))
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, combo=combo, item_type="combo", quantity=1)
        ProductCombo.objects.filter(pk=combo.pk).update(is_active=False)
        r = authenticated_client.post(URL, ADDR, format="json")
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
# G2
# --------------------------------------------------------------------------- #
@pytest.mark.django_db
class TestComboComponentStock:
    def test_combo_blocked_when_component_out_of_stock(self, authenticated_client, test_user, test_category):
        a = _product(test_category, "CompA", stock=0)        # out of stock
        b = _product(test_category, "CompB", stock=5)
        combo = _combo("OOS Combo", (a, 1), (b, 1))
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, combo=combo, item_type="combo", quantity=1)
        r = authenticated_client.post(URL, ADDR, format="json")
        assert r.status_code == 400
        assert "CompA" in r.json().get("error", "")
        assert not Order.objects.filter(user=test_user).exists()

    def test_combo_decrements_component_stock(self, authenticated_client, test_user, test_category):
        a = _product(test_category, "CompA", stock=10)
        b = _product(test_category, "CompB", stock=10)
        combo = _combo("Box", (a, 2), (b, 1))                # 2×A + 1×B per combo
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, combo=combo, item_type="combo", quantity=3)  # ×3
        r = authenticated_client.post(URL, ADDR, format="json")
        assert r.status_code == 201
        a.refresh_from_db(); b.refresh_from_db()
        assert a.stock == 10 - (2 * 3)   # 4
        assert b.stock == 10 - (1 * 3)   # 7

    def test_combo_exceeding_component_stock_blocked(self, authenticated_client, test_user, test_category):
        a = _product(test_category, "CompA", stock=5)
        combo = _combo("Box2", (a, 2))                       # needs 2×A per combo
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, combo=combo, item_type="combo", quantity=3)  # needs 6 > 5
        r = authenticated_client.post(URL, ADDR, format="json")
        assert r.status_code == 400
        a.refresh_from_db()
        assert a.stock == 5              # untouched

    def test_cancel_restores_component_stock(self, authenticated_client, test_user, test_category):
        a = _product(test_category, "CompA", stock=10)
        combo = _combo("Box3", (a, 2))
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, combo=combo, item_type="combo", quantity=2)  # consumes 4
        create = authenticated_client.post(URL, ADDR, format="json")
        assert create.status_code == 201
        a.refresh_from_db()
        assert a.stock == 6
        order = Order.objects.get(user=test_user)
        cancel = authenticated_client.post(f"{URL}{order.id}/cancel/")
        assert cancel.status_code == 200
        a.refresh_from_db()
        assert a.stock == 10             # fully restored
