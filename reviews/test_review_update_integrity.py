"""
Regression tests for G7 — a verified review must stay attached to the item it
was written for.

Without `perform_update` guarding the subject, a user could PATCH a legitimately
verified review onto a product/combo they never bought (is_verified_purchase is
read-only and stays True), manufacturing fake "verified" reviews. The subject
(item_type/product/combo) is now immutable on update; rating/title/comment may
still be edited.
"""
from decimal import Decimal

import pytest

from conftest import create_test_image
from products.models import Product
from orders.models import Order, OrderItem
from reviews.models import Review

URL = "/api/reviews/"


def _product(cat, name):
    return Product.objects.create(
        name=name, category=cat, description="x", price=Decimal("100.00"), stock=10,
        weight=Decimal("250.00"), unit="g", spice_form="powder", is_active=True,
        image=create_test_image(f"{name}.jpg"),
    )


def _delivered(user, product):
    order = Order.objects.create(
        user=user, shipping_address="a", phone_number="1", payment_method="COD",
        subtotal=Decimal("100.00"), tax=Decimal("5.00"), total_amount=Decimal("105.00"),
        status="delivered",
    )
    OrderItem.objects.create(
        order=order, product=product, item_type="product", product_name=product.name,
        product_weight=product.weight, quantity=1, price=product.final_price,
        final_price=product.final_price,
    )


@pytest.mark.django_db
class TestReviewSubjectImmutable:
    def _make_verified_review(self, client, user, cat):
        bought = _product(cat, "Bought")
        _delivered(user, bought)
        r = client.post(URL, {"item_type": "product", "product": bought.id,
                              "rating": 5, "title": "t", "comment": "c"}, format="json")
        assert r.status_code == 201
        return r.json()["id"], bought

    def test_cannot_reassign_review_to_unpurchased_product(self, authenticated_client, test_user, test_category):
        rid, bought = self._make_verified_review(authenticated_client, test_user, test_category)
        not_bought = _product(test_category, "NotBought")
        patch = authenticated_client.patch(f"{URL}{rid}/", {"product": not_bought.id}, format="json")
        assert patch.status_code == 400
        rev = Review.objects.get(id=rid)
        assert rev.product_id == bought.id            # unchanged
        assert rev.is_verified_purchase is True

    def test_can_still_edit_rating_and_comment(self, authenticated_client, test_user, test_category):
        rid, _bought = self._make_verified_review(authenticated_client, test_user, test_category)
        patch = authenticated_client.patch(
            f"{URL}{rid}/", {"rating": 3, "comment": "updated"}, format="json")
        assert patch.status_code == 200
        rev = Review.objects.get(id=rid)
        assert rev.rating == 3 and rev.comment == "updated"

    def test_cannot_change_item_type(self, authenticated_client, test_user, test_category):
        rid, _bought = self._make_verified_review(authenticated_client, test_user, test_category)
        patch = authenticated_client.patch(f"{URL}{rid}/", {"item_type": "combo"}, format="json")
        assert patch.status_code == 400
