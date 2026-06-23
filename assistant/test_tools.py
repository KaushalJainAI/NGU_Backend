"""Unit tests for the new assistant catalogue + order tools.

Focus areas:
  - happy paths for browse_products / get_product_reviews / list_my_orders / get_order_details
  - G1 isolation: a user can never read another user's orders (no oracle)
  - G2 field hygiene: catalogue + review tools never leak internal / private fields
  - sad payloads: bad args, unknown slugs, anonymous access
"""
import pytest
from decimal import Decimal

from assistant import tools as toolkit


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def discounted_product(db, test_category):
    from products.models import Product
    return Product.objects.create(
        name='Discounted Chilli Powder',
        category=test_category,
        description='On offer',
        price=Decimal('200.00'),
        discount_price=Decimal('120.00'),
        stock=10,
        weight=Decimal('100.00'),
        unit='g',
        spice_form='powder',
        is_active=True,
    )


@pytest.fixture
def review_for_product(db, test_product, test_user):
    from reviews.models import Review
    return Review.objects.create(
        item_type='product', product=test_product, user=test_user,
        rating=4, title='Good stuff', comment='Fresh and aromatic',
        is_verified_purchase=True,
    )


# --------------------------------------------------------------------------- #
# browse_products
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestBrowseProducts:
    def test_returns_active_products(self, test_product, test_product2):
        out = toolkit.tool_browse_products(None, {})
        names = {r['name'] for r in out['results']}
        assert test_product.name in names and test_product2.name in names

    def test_excludes_inactive(self, test_product, test_category):
        from products.models import Product
        Product.objects.create(
            name='Hidden Spice', category=test_category, description='x',
            price=Decimal('50'), stock=5, weight=Decimal('100'), unit='g',
            spice_form='powder', is_active=False,
        )
        out = toolkit.tool_browse_products(None, {})
        assert 'Hidden Spice' not in {r['name'] for r in out['results']}

    def test_max_price_filter(self, test_product, test_product2):
        # test_product final 120, test_product2 final 200
        out = toolkit.tool_browse_products(None, {'max_price': 150, 'include_combos': False})
        prices = [r['price'] for r in out['results']]
        assert prices and all(p <= 150 for p in prices)

    def test_on_offer_filter(self, discounted_product, test_product2):
        # test_product2 has no discount_price; discounted_product does.
        out = toolkit.tool_browse_products(None, {'on_offer': True, 'include_combos': False})
        names = {r['name'] for r in out['results']}
        assert 'Discounted Chilli Powder' in names
        assert 'Test Cumin Seeds' not in names

    def test_spice_form_filter(self, test_product, test_product2):
        # test_product is 'powder', test_product2 is 'whole'
        out = toolkit.tool_browse_products(None, {'spice_form': 'whole', 'include_combos': False})
        names = {r['name'] for r in out['results']}
        assert 'Test Cumin Seeds' in names
        assert 'Test Turmeric Powder' not in names

    def test_sort_price_asc(self, test_product, test_product2):
        out = toolkit.tool_browse_products(None, {'sort': 'price_asc', 'include_combos': False})
        prices = [r['price'] for r in out['results']]
        assert prices == sorted(prices)

    def test_limit_is_capped(self, test_product):
        out = toolkit.tool_browse_products(None, {'limit': 9999})
        assert len(out['results']) <= toolkit.MAX_LIST_LIMIT

    def test_combos_included_by_default(self, test_combo):
        out = toolkit.tool_browse_products(None, {})
        types = {r['type'] for r in out['results']}
        assert 'combo' in types

    def test_only_public_fields(self, test_product):
        out = toolkit.tool_browse_products(None, {'include_combos': False})
        allowed = {'id', 'name', 'slug', 'type', 'price', 'original_price', 'in_stock', 'route'}
        for r in out['results']:
            assert set(r).issubset(allowed)
            assert 'stock' not in r and 'cost' not in r


# --------------------------------------------------------------------------- #
# get_product_reviews
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestGetProductReviews:
    def test_returns_summary_and_recent(self, test_product, review_for_product):
        out = toolkit.tool_get_product_reviews(None, {'slug': test_product.slug})
        assert out['review_count'] == 1
        assert out['average_rating'] == 4.0
        assert out['reviews'][0]['comment'] == 'Fresh and aromatic'
        assert out['reviews'][0]['verified_purchase'] is True

    def test_does_not_leak_reviewer_email(self, test_product, review_for_product, test_user):
        out = toolkit.tool_get_product_reviews(None, {'slug': test_product.slug})
        blob = str(out)
        assert test_user.email not in blob
        # Only the first name is exposed as 'reviewer'.
        assert out['reviews'][0]['reviewer'] == test_user.first_name

    def test_no_reviews_yet(self, test_product):
        out = toolkit.tool_get_product_reviews(None, {'slug': test_product.slug})
        assert out['review_count'] == 0
        assert out['average_rating'] is None
        assert out['reviews'] == []

    def test_unknown_slug(self):
        out = toolkit.tool_get_product_reviews(None, {'slug': 'no-such-thing'})
        assert out['error'] == 'not_found'

    def test_missing_slug(self):
        out = toolkit.tool_get_product_reviews(None, {})
        assert out['error'] == 'bad_args'


# --------------------------------------------------------------------------- #
# list_my_orders
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestListMyOrders:
    def test_anonymous_blocked(self):
        assert toolkit.tool_list_my_orders(None, {})['error'] == 'login_required'

    def test_lists_own_orders(self, test_order, test_user):
        out = toolkit.tool_list_my_orders(test_user, {})
        assert out['count'] == 1
        assert out['orders'][0]['order_number'] == f'ORD-{test_order.id:06d}'
        assert out['orders'][0]['item_count'] == 1

    def test_does_not_list_other_users_orders(self, test_order, test_user2):
        # test_order belongs to test_user; test_user2 must see nothing.
        out = toolkit.tool_list_my_orders(test_user2, {})
        assert out['count'] == 0
        assert out['orders'] == []

    def test_limit_capped(self, test_user):
        out = toolkit.tool_list_my_orders(test_user, {'limit': 9999})
        assert len(out['orders']) <= toolkit.MAX_LIST_LIMIT


# --------------------------------------------------------------------------- #
# get_order_details
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestGetOrderDetails:
    def test_anonymous_blocked(self):
        out = toolkit.tool_get_order_details(None, {'order_number': 'ORD-000001'})
        assert out['error'] == 'login_required'

    def test_own_order_items(self, test_order, test_user, test_product):
        num = f'ORD-{test_order.id:06d}'
        out = toolkit.tool_get_order_details(test_user, {'order_number': num})
        assert out['order_number'] == num
        assert len(out['items']) == 1
        item = out['items'][0]
        assert item['name'] == test_product.name
        assert item['item_type'] == 'product'
        assert item['product_id'] == test_product.id
        assert item['quantity'] == 2

    def test_other_users_order_is_not_found(self, test_order, test_user2):
        """G1: no existence oracle — another user's order looks identical to a
        non-existent one."""
        num = f'ORD-{test_order.id:06d}'
        out = toolkit.tool_get_order_details(test_user2, {'order_number': num})
        assert out['error'] == 'not_found'

    def test_injected_user_id_is_ignored(self, test_order, test_user, test_user2):
        num = f'ORD-{test_order.id:06d}'
        out = toolkit.tool_get_order_details(
            test_user2, {'order_number': num, 'user_id': test_user.id, 'email': test_user.email}
        )
        assert out['error'] == 'not_found'

    def test_bad_order_number(self, test_user):
        out = toolkit.tool_get_order_details(test_user, {'order_number': 'garbage'})
        assert out['error'] == 'bad_args'


# --------------------------------------------------------------------------- #
# Registry wiring
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestRegistry:
    def test_new_tools_registered(self):
        for name in ('browse_products', 'get_product_reviews',
                     'list_my_orders', 'get_order_details'):
            assert name in toolkit.READ_TOOLS
            assert name in toolkit.ALL_TOOL_NAMES

    def test_still_no_enumeration_of_users(self):
        for forbidden in ('list_users', 'search_customers', 'list_all_orders'):
            assert forbidden not in toolkit.ALL_TOOL_NAMES

    def test_run_read_tool_dispatches_new_tool(self, test_product):
        out = toolkit.run_read_tool('browse_products', None, {'include_combos': False})
        assert 'results' in out
