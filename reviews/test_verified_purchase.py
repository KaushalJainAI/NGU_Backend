"""
Verified-purchase gating for reviews — the rule that stops fake/abusive reviews.

A user may only review an item they bought, and only when that order has reached
a fulfilment status. Covers the full status matrix (pending blocked; confirmed/
processing/shipped/delivering/delivered allowed; cancelled blocked), plus
"never ordered" and cross-user purchase isolation.
"""
from decimal import Decimal

import pytest

from orders.models import Order, OrderItem

URL = "/api/reviews/"


def _order_with(product, user, status):
    order = Order.objects.create(
        user=user, shipping_address="1 Rd", phone_number="1234567890",
        payment_method="COD", subtotal=Decimal("120.00"), tax=Decimal("6.00"),
        total_amount=Decimal("126.00"), status=status,
    )
    OrderItem.objects.create(
        order=order, product=product, item_type="product",
        product_name=product.name, product_weight=product.weight,
        quantity=1, price=product.final_price, final_price=product.final_price,
    )
    return order


def _review_payload(product, rating=5):
    return {"item_type": "product", "product": product.id, "rating": rating,
            "title": "Nice", "comment": "Fresh and aromatic"}


@pytest.mark.django_db
class TestVerifiedPurchaseGate:
    def test_never_ordered_is_blocked(self, authenticated_client, test_product):
        r = authenticated_client.post(URL, _review_payload(test_product), format="json")
        assert r.status_code == 400

    @pytest.mark.parametrize("good_status", ["confirmed", "processing", "shipped", "delivering", "delivered"])
    def test_fulfilment_statuses_allow_review(self, authenticated_client, test_user, test_product, good_status):
        _order_with(test_product, test_user, good_status)
        r = authenticated_client.post(URL, _review_payload(test_product), format="json")
        assert r.status_code == 201, r.content
        assert r.json().get("is_verified_purchase") is True

    @pytest.mark.parametrize("bad_status", ["pending", "cancelled"])
    def test_non_fulfilled_statuses_block_review(self, authenticated_client, test_user, test_product, bad_status):
        _order_with(test_product, test_user, bad_status)
        r = authenticated_client.post(URL, _review_payload(test_product), format="json")
        assert r.status_code == 400

    def test_another_users_purchase_does_not_count(self, authenticated_client, test_user2, test_product):
        # test_user2 bought it (delivered), but the *authenticated* user (test_user) did not.
        _order_with(test_product, test_user2, "delivered")
        r = authenticated_client.post(URL, _review_payload(test_product), format="json")
        assert r.status_code == 400

    def test_duplicate_review_blocked_after_valid_one(self, authenticated_client, test_user, test_product):
        _order_with(test_product, test_user, "delivered")
        first = authenticated_client.post(URL, _review_payload(test_product), format="json")
        assert first.status_code == 201
        second = authenticated_client.post(URL, _review_payload(test_product, rating=3), format="json")
        assert second.status_code == 400

    @pytest.mark.parametrize("bad_rating", [0, -1, 6, 99])
    def test_rating_out_of_bounds_rejected(self, authenticated_client, test_user, test_product, bad_rating):
        _order_with(test_product, test_user, "delivered")
        r = authenticated_client.post(URL, _review_payload(test_product, rating=bad_rating), format="json")
        assert r.status_code == 400

    @pytest.mark.parametrize("ok_rating", [1, 5])
    def test_rating_boundaries_accepted(self, authenticated_client, test_user, test_product, ok_rating):
        _order_with(test_product, test_user, "delivered")
        r = authenticated_client.post(URL, _review_payload(test_product, rating=ok_rating), format="json")
        assert r.status_code == 201
