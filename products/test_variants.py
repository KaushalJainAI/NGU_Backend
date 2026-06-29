"""Tests for the multiple-packaging (ProductVariant) feature across
products API, cart, and orders."""
import pytest
from decimal import Decimal

from rest_framework import status

from products.models import ProductVariant
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem


@pytest.fixture
def product_with_variants(db, test_product):
    """test_product (250g default) plus a 500g and 1kg variant.

    The conftest test_product already gets one is_default variant via the
    backfill migration in real DBs, but tests run on a fresh schema where the
    data migration created nothing, so make the default explicit here."""
    default = ProductVariant.objects.create(
        product=test_product, weight=Decimal('250'), unit='g',
        price=Decimal('150.00'), discount_price=Decimal('120.00'),
        stock=100, is_default=True, display_order=0,
    )
    big = ProductVariant.objects.create(
        product=test_product, weight=Decimal('500'), unit='g',
        price=Decimal('280.00'), discount_price=Decimal('230.00'),
        stock=40, display_order=1,
    )
    huge = ProductVariant.objects.create(
        product=test_product, weight=Decimal('1'), unit='kg',
        price=Decimal('520.00'), stock=10, display_order=2,
    )
    return test_product, default, big, huge


@pytest.mark.django_db
class TestProductVariantAPI:
    base_url = '/api/products/'

    def test_detail_includes_variants(self, api_client, product_with_variants):
        product, default, big, huge = product_with_variants
        resp = api_client.get(f'{self.base_url}{product.slug}/')
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data['variant_count'] == 3
        slugs = [v['slug'] for v in data['variants']]
        assert big.slug in slugs and huge.slug in slugs
        # ordered by display_order
        assert data['variants'][0]['id'] == default.id
        assert data['variants'][1]['id'] == big.id
        # variant carries its own pricing
        v500 = next(v for v in data['variants'] if v['id'] == big.id)
        assert v500['final_price'] == 230.0
        assert v500['formatted_weight'] == '500g'

    def test_variant_slug_resolves_to_product(self, api_client, product_with_variants):
        product, default, big, huge = product_with_variants
        resp = api_client.get(f'{self.base_url}{big.slug}/')
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        # Returns the parent product, with the requested size pre-selected
        assert data['id'] == product.id
        assert data['selected_variant_id'] == big.id


@pytest.mark.django_db
class TestCartVariants:
    base_url = '/api/cart/'

    def test_add_with_variant_uses_variant_price(self, authenticated_client, product_with_variants):
        product, default, big, huge = product_with_variants
        resp = authenticated_client.post(
            f'{self.base_url}add_item/',
            {'product_id': product.id, 'variant_id': big.id, 'quantity': 2},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        item = data['items'][0]
        assert item['variant_id'] == big.id
        assert item['price'] == 230.0          # variant discounted price
        assert item['weight'] == '500g'
        assert data['summary']['subtotal'] == 460.0  # 230 * 2

    def test_default_variant_when_unspecified(self, authenticated_client, product_with_variants):
        product, default, big, huge = product_with_variants
        resp = authenticated_client.post(
            f'{self.base_url}add_item/',
            {'product_id': product.id, 'quantity': 1},
            format='json',
        )
        assert resp.status_code == status.HTTP_200_OK
        item = resp.json()['items'][0]
        assert item['variant_id'] == default.id

    def test_two_sizes_are_separate_lines(self, authenticated_client, product_with_variants):
        product, default, big, huge = product_with_variants
        authenticated_client.post(
            f'{self.base_url}add_item/',
            {'product_id': product.id, 'variant_id': big.id, 'quantity': 1},
            format='json',
        )
        resp = authenticated_client.post(
            f'{self.base_url}add_item/',
            {'product_id': product.id, 'variant_id': huge.id, 'quantity': 1},
            format='json',
        )
        data = resp.json()
        assert len(data['items']) == 2
        variant_ids = {i['variant_id'] for i in data['items']}
        assert variant_ids == {big.id, huge.id}

    def test_variant_stock_enforced(self, authenticated_client, product_with_variants):
        product, default, big, huge = product_with_variants
        resp = authenticated_client.post(
            f'{self.base_url}add_item/',
            {'product_id': product.id, 'variant_id': huge.id, 'quantity': 999},
            format='json',
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestOrderVariants:
    base_url = '/api/orders/'

    def test_order_decrements_variant_stock_and_mirrors_default(
        self, authenticated_client, test_user, product_with_variants
    ):
        product, default, big, huge = product_with_variants
        cart, _ = Cart.objects.get_or_create(user=test_user)
        # buy 3 of the 500g (non-default) and 2 of the default
        CartItem.objects.create(cart=cart, product=product, variant=big,
                                item_type='product', quantity=3)
        CartItem.objects.create(cart=cart, product=product, variant=default,
                                item_type='product', quantity=2)

        resp = authenticated_client.post(
            self.base_url,
            {'shipping_address': '1 Test Rd', 'phone_number': '1234567890',
             'payment_method': 'COD'},
            format='json',
        )
        assert resp.status_code == status.HTTP_201_CREATED

        big.refresh_from_db()
        default.refresh_from_db()
        product.refresh_from_db()
        assert big.stock == 37          # 40 - 3
        assert default.stock == 98      # 100 - 2
        # default variant mirrors to legacy Product.stock; non-default does not
        assert product.stock == 98

        # order item snapshots the variant weight + price
        oi = OrderItem.objects.get(order_id=resp.json()['order_id'], variant=big)
        assert oi.product_weight == '500g'
        assert oi.price == Decimal('230.00')
        assert oi.variant_id == big.id

    def test_cancel_restores_variant_stock(
        self, authenticated_client, test_user, product_with_variants
    ):
        product, default, big, huge = product_with_variants
        cart, _ = Cart.objects.get_or_create(user=test_user)
        CartItem.objects.create(cart=cart, product=product, variant=big,
                                item_type='product', quantity=5)
        order_id = authenticated_client.post(
            self.base_url,
            {'shipping_address': '1 Test Rd', 'phone_number': '1234567890',
             'payment_method': 'COD'},
            format='json',
        ).json()['order_id']
        big.refresh_from_db()
        assert big.stock == 35

        authenticated_client.post(f'{self.base_url}{order_id}/cancel/')
        big.refresh_from_db()
        assert big.stock == 40
