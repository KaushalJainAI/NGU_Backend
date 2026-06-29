"""
Tests for the analytics insights system: anonymous counters, the rollup
command, and the admin-only insights API.

Runs on the default test settings (SQLite + LocMemCache). Because there is no
Redis, ``record_anon`` writes straight to DailyAnonStat and ``flush_anon_to_db``
is a no-op — this exercises the same dimension-building and aggregation logic
used in production.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from analytics.anon import record_anon, _device, _source
from analytics.models import (
    DailyAnonStat, DailyFunnelRollup, DailySalesRollup, SearchTermStat, UserEvent,
)
from analytics import insights
from orders.models import Order, OrderItem


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _make_order(user, when, total, status='confirmed', coupon=None, discount=0):
    order = Order.objects.create(
        user=user,
        shipping_address='addr',
        phone_number='123',
        payment_method='COD',
        subtotal=Decimal(total),
        discount_amount=Decimal(discount),
        total_amount=Decimal(total),
        status=status,
        coupon=coupon,
    )
    # created_at is auto_now_add; force it to the desired instant.
    Order.objects.filter(pk=order.pk).update(created_at=when)
    order.refresh_from_db()
    return order


def _rf(user_agent='Mozilla/5.0 (Windows NT 10.0)', referer='', remote='8.8.8.8'):
    """A minimal request-like object for record_anon (avoids HTTP overhead)."""
    from django.test import RequestFactory
    req = RequestFactory().post('/api/anon-events/')
    req.META['HTTP_USER_AGENT'] = user_agent
    if referer:
        req.META['HTTP_REFERER'] = referer
    req.META['REMOTE_ADDR'] = remote
    return req


# --------------------------------------------------------------------------- #
# anonymous counters
# --------------------------------------------------------------------------- #

class TestAnonHelpers:
    def test_device_classification(self):
        assert _device('iPhone Mobile Safari') == 'mobile'
        assert _device('Mozilla/5.0 (Windows NT 10.0)') == 'desktop'
        assert _device('Googlebot/2.1') == 'bot'
        assert _device('Mozilla/5.0 (iPad; ...)') == 'tablet'

    def test_source_buckets(self):
        assert _source('', 'shop.com') == 'direct'
        assert _source('https://www.google.com/search', 'shop.com') == 'google'
        assert _source('https://facebook.com/x', 'shop.com') == 'social'
        assert _source('https://blog.example.com', 'shop.com') == 'referral'
        # internal navigation is not a traffic source
        assert _source('https://shop.com/cart', 'shop.com') is None


@pytest.mark.django_db
class TestRecordAnon:
    def test_increments_total_and_device(self):
        record_anon('page_view', _rf())
        total = DailyAnonStat.objects.get(
            date=timezone.localdate(), metric='page_view', dimension_key='')
        device = DailyAnonStat.objects.get(
            date=timezone.localdate(), metric='page_view', dimension_key='device:desktop')
        assert total.count == 1
        assert device.count == 1

    def test_repeated_events_accumulate_not_explode(self):
        for _ in range(5):
            record_anon('page_view', _rf())
        # 5 events, still ONE row per (metric, dimension) — bounded storage.
        total = DailyAnonStat.objects.get(
            date=timezone.localdate(), metric='page_view', dimension_key='')
        assert total.count == 5
        assert DailyAnonStat.objects.filter(metric='page_view', dimension_key='').count() == 1

    def test_zero_result_search_bumps_extra_metric(self):
        record_anon('search', _rf(), query='asdfqwer', zero=True)
        assert DailyAnonStat.objects.filter(metric='search', dimension_key='').exists()
        assert DailyAnonStat.objects.filter(metric='search_zero_result', dimension_key='').exists()

    def test_disallowed_metric_is_ignored(self):
        record_anon('totally_made_up', _rf())
        assert DailyAnonStat.objects.count() == 0

    def test_bot_bucketed_separately(self):
        record_anon('page_view', _rf(user_agent='Googlebot/2.1'))
        assert DailyAnonStat.objects.filter(dimension_key='device:bot').exists()


@pytest.mark.django_db
class TestAnonEndpoint:
    def test_anonymous_user_can_post_and_gets_204(self, api_client):
        resp = api_client.post('/api/anon-events/', {'metric': 'page_view'}, format='json')
        assert resp.status_code == 204
        assert DailyAnonStat.objects.filter(metric='page_view').exists()

    def test_bad_metric_still_204_no_row(self, api_client):
        resp = api_client.post('/api/anon-events/', {'metric': 'nope'}, format='json')
        assert resp.status_code == 204
        assert DailyAnonStat.objects.count() == 0


# --------------------------------------------------------------------------- #
# rollup command
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestRollupCommand:
    def test_sales_rollup_basic(self, test_user, test_coupon):
        today = timezone.localdate()
        now = timezone.now()
        _make_order(test_user, now, '100.00')
        _make_order(test_user, now, '300.00', coupon=test_coupon, discount='30.00')
        # cancelled orders are excluded from realised revenue
        _make_order(test_user, now, '999.00', status='cancelled')

        call_command('rollup_analytics', '--date', today.isoformat())

        roll = DailySalesRollup.objects.get(date=today)
        assert roll.orders == 2
        assert roll.revenue == Decimal('400.00')
        assert roll.coupon_orders == 1
        assert roll.aov == Decimal('200.00')

    def test_new_vs_returning(self, test_user, test_user2):
        today = timezone.localdate()
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        # test_user ordered yesterday and today -> returning today
        _make_order(test_user, yesterday, '50.00')
        _make_order(test_user, now, '50.00')
        # test_user2 first ever order is today -> new
        _make_order(test_user2, now, '70.00')

        call_command('rollup_analytics', '--date', today.isoformat())
        roll = DailySalesRollup.objects.get(date=today)
        assert roll.new_customers == 1
        assert roll.returning_customers == 1

    def test_funnel_and_search_rollup(self, test_user, test_product):
        today = timezone.localdate()
        UserEvent.objects.create(user=test_user, event_type='view', product=test_product)
        UserEvent.objects.create(user=test_user, event_type='view', product=test_product)
        UserEvent.objects.create(user=test_user, event_type='add_to_cart', product=test_product)
        UserEvent.objects.create(user=test_user, event_type='search', query='Turmeric',
                                 metadata={'zero': False})
        UserEvent.objects.create(user=test_user, event_type='search', query='xyzzy',
                                 metadata={'zero': True})

        call_command('rollup_analytics', '--date', today.isoformat())

        assert DailyFunnelRollup.objects.get(date=today, event_type='view').count == 2
        assert DailyFunnelRollup.objects.get(date=today, event_type='add_to_cart').count == 1
        assert SearchTermStat.objects.get(date=today, term='turmeric').count == 1
        assert SearchTermStat.objects.get(date=today, term='xyzzy').zero_result is True

    def test_idempotent_rerun(self, test_user):
        today = timezone.localdate()
        _make_order(test_user, timezone.now(), '100.00')
        call_command('rollup_analytics', '--date', today.isoformat())
        call_command('rollup_analytics', '--date', today.isoformat())
        # Re-run must not double-count.
        assert DailySalesRollup.objects.filter(date=today).count() == 1
        assert DailySalesRollup.objects.get(date=today).orders == 1


# --------------------------------------------------------------------------- #
# insights aggregation + API
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestInsightsAggregation:
    def test_sales_pop_delta(self, test_user):
        today = timezone.localdate()
        # current window (today): revenue 100; previous day: revenue 50 -> +100%
        DailySalesRollup.objects.create(date=today, orders=1, revenue=Decimal('100'))
        DailySalesRollup.objects.create(date=today - timedelta(days=1), orders=1,
                                        revenue=Decimal('50'))
        data = insights.sales(today, today, 'day')
        assert data['kpis']['revenue'] == 100.0
        assert data['kpis']['revenue_delta_pct'] == 100.0

    def test_funnel_conversion(self):
        today = timezone.localdate()
        DailyFunnelRollup.objects.create(date=today, event_type='view', count=100)
        DailyFunnelRollup.objects.create(date=today, event_type='add_to_cart', count=40)
        DailyFunnelRollup.objects.create(date=today, event_type='purchase', count=10)
        data = insights.funnel(today, today)
        stages = {s['stage']: s for s in data['stages']}
        assert stages['add_to_cart']['pct_of_top'] == 40.0
        assert stages['purchase']['count'] == 10

    def test_anonymous_macro_funnel_and_breakdowns(self):
        today = timezone.localdate()
        DailyAnonStat.objects.create(date=today, metric='page_view', dimension_key='', count=200)
        DailyAnonStat.objects.create(date=today, metric='page_view',
                                     dimension_key='device:mobile', count=150)
        DailyAnonStat.objects.create(date=today, metric='page_view',
                                     dimension_key='state:Maharashtra', count=120)
        DailyAnonStat.objects.create(date=today, metric='product_view', dimension_key='', count=80)
        data = insights.anonymous(today, today)
        assert data['totals']['page_view'] == 200
        assert {d['device']: d['count'] for d in data['by_device']}['mobile'] == 150
        assert {d['state']: d['count'] for d in data['by_state']}['Maharashtra'] == 120
        macro = {s['stage']: s for s in data['macro_funnel']}
        assert macro['product_view']['pct_of_top'] == 40.0


@pytest.mark.django_db
class TestInsightsAPI:
    def test_requires_admin(self, authenticated_client):
        resp = authenticated_client.get('/api/analytics/sales/')
        assert resp.status_code == 403

    def test_anonymous_user_denied(self, api_client):
        resp = api_client.get('/api/analytics/sales/')
        assert resp.status_code in (401, 403)

    def test_admin_can_read_all_endpoints(self, admin_client, test_user):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=2, revenue=Decimal('500'))
        for path in ['sales', 'funnel', 'search', 'customers', 'anonymous']:
            resp = admin_client.get(f'/api/analytics/{path}/')
            assert resp.status_code == 200, f'{path} -> {resp.status_code}'

    def test_sales_endpoint_returns_kpis(self, admin_client):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=2, revenue=Decimal('500'), units=5)
        resp = admin_client.get('/api/analytics/sales/',
                                {'from': today.isoformat(), 'to': today.isoformat()})
        assert resp.status_code == 200
        assert resp.data['kpis']['revenue'] == 500.0
        assert resp.data['kpis']['orders'] == 2
