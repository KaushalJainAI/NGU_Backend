"""
Extended coverage for the analytics insights system: granularity bucketing,
date-param parsing, caching, the customers/search endpoints, anonymous source
classification, and the decoupled purchase-capture signal.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.utils import timezone

from analytics import insights
from analytics.anon import record_anon
from analytics.models import (
    DailyAnonStat, DailySalesRollup, UserEvent,
)
from orders.models import Order, OrderItem


def _rf(referer='', user_agent='Mozilla/5.0 (Windows NT 10.0)'):
    from django.test import RequestFactory
    req = RequestFactory().post('/api/anon-events/')
    req.META['HTTP_USER_AGENT'] = user_agent
    if referer:
        req.META['HTTP_REFERER'] = referer
    req.META['REMOTE_ADDR'] = '8.8.8.8'
    return req


# --------------------------------------------------------------------------- #
# granularity bucketing
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestGranularity:
    def test_weekly_buckets_collapse_days(self):
        # Three consecutive days in the same ISO week roll into one bucket.
        monday = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        for i in range(3):
            DailySalesRollup.objects.create(
                date=monday + timedelta(days=i), orders=1, revenue=Decimal('10'))
        data = insights.sales(monday, monday + timedelta(days=2), 'week')
        assert len(data['series']) == 1
        assert data['series'][0]['revenue'] == 30.0

    def test_monthly_buckets(self):
        first = timezone.localdate().replace(day=1)
        DailySalesRollup.objects.create(date=first, orders=1, revenue=Decimal('5'))
        DailySalesRollup.objects.create(date=first + timedelta(days=1), orders=1,
                                        revenue=Decimal('7'))
        data = insights.sales(first, first + timedelta(days=1), 'month')
        assert len(data['series']) == 1
        assert data['series'][0]['revenue'] == 12.0


# --------------------------------------------------------------------------- #
# period-over-period edge cases
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestDeltas:
    def test_delta_none_when_no_prior_baseline(self):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=1, revenue=Decimal('100'))
        data = insights.sales(today, today, 'day')
        # No previous window data -> delta undefined (None), not a crash.
        assert data['kpis']['revenue_delta_pct'] is None

    def test_empty_range_is_zeroed(self):
        today = timezone.localdate()
        data = insights.sales(today, today, 'day')
        assert data['kpis']['revenue'] == 0
        assert data['kpis']['aov'] == 0
        assert data['series'] == []


# --------------------------------------------------------------------------- #
# customers + search aggregation
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestCustomersAndSearch:
    def test_repeat_rate(self):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=4, revenue=Decimal('100'),
                                        new_customers=1, returning_customers=3)
        data = insights.customers(today, today, 'day')
        assert data['kpis']['repeat_rate_pct'] == 75.0
        assert data['kpis']['new_customers'] == 1

    def test_top_customers_and_geo(self, test_user, test_product):
        from analytics.models import UserGeo
        UserGeo.objects.create(user=test_user, state='Maharashtra')
        order = Order.objects.create(
            user=test_user, shipping_address='a', phone_number='1',
            payment_method='COD', subtotal=Decimal('200'), total_amount=Decimal('200'),
            status='confirmed')
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now())
        today = timezone.localdate()
        data = insights.customers(today, today, 'day')
        assert any(c['email'] == test_user.email for c in data['top_customers'])
        assert any(g['state'] == 'Maharashtra' for g in data['geo'])

    def test_viewed_not_bought_excludes_purchased(self, test_user, test_product, test_product2):
        # product viewed but never purchased -> appears
        UserEvent.objects.create(user=test_user, event_type='view', product=test_product)
        # product2 viewed AND purchased -> excluded
        UserEvent.objects.create(user=test_user, event_type='view', product=test_product2)
        UserEvent.objects.create(user=test_user, event_type='purchase', product=test_product2)
        today = timezone.localdate()
        data = insights.search(today, today)
        ids = [r['product_id'] for r in data['viewed_not_bought']]
        assert test_product.id in ids
        assert test_product2.id not in ids


# --------------------------------------------------------------------------- #
# anonymous source classification through the full record path
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestAnonSource:
    def test_referer_drives_source_dimension(self):
        record_anon('page_view', _rf(referer='https://www.google.com/search?q=spice'))
        assert DailyAnonStat.objects.filter(
            metric='page_view', dimension_key='source:google').exists()

    def test_direct_when_no_referer(self):
        record_anon('page_view', _rf())
        assert DailyAnonStat.objects.filter(
            metric='page_view', dimension_key='source:direct').exists()


# --------------------------------------------------------------------------- #
# date-param parsing + caching at the view layer
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestViewParams:
    def test_invalid_dates_fall_back_to_default(self, admin_client):
        resp = admin_client.get('/api/analytics/sales/',
                                {'from': 'garbage', 'to': 'also-bad'})
        assert resp.status_code == 200  # defaults applied, no 500

    def test_invalid_granularity_defaults_to_day(self, admin_client):
        resp = admin_client.get('/api/analytics/sales/', {'granularity': 'decade'})
        assert resp.status_code == 200
        assert resp.data['range']['granularity'] == 'day'

    def test_overview_endpoint(self, admin_client):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=3, revenue=Decimal('300'),
                                        new_customers=1, returning_customers=2)
        resp = admin_client.get('/api/analytics/overview/',
                                {'from': today.isoformat(), 'to': today.isoformat()})
        assert resp.status_code == 200
        assert resp.data['kpis']['revenue'] == 300.0
        assert resp.data['kpis']['repeat_rate_pct'] == 66.7
        assert 'funnel' in resp.data and 'anon_by_device' in resp.data

    def test_overview_requires_admin(self, authenticated_client):
        assert authenticated_client.get('/api/analytics/overview/').status_code == 403

    def test_response_is_cached(self, admin_client):
        today = timezone.localdate()
        DailySalesRollup.objects.create(date=today, orders=1, revenue=Decimal('100'))
        params = {'from': today.isoformat(), 'to': today.isoformat()}
        first = admin_client.get('/api/analytics/sales/', params)
        assert first.data['kpis']['revenue'] == 100.0
        # Mutate underlying data; cached response should be unchanged within TTL.
        DailySalesRollup.objects.filter(date=today).update(revenue=Decimal('999'))
        second = admin_client.get('/api/analytics/sales/', params)
        assert second.data['kpis']['revenue'] == 100.0


# --------------------------------------------------------------------------- #
# decoupled purchase-capture signal
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
class TestPurchaseSignal:
    def test_order_creation_records_purchase_events(
        self, test_user, test_product, django_capture_on_commit_callbacks,
    ):
        with django_capture_on_commit_callbacks(execute=True):
            order = Order.objects.create(
                user=test_user, shipping_address='a', phone_number='1',
                payment_method='COD', subtotal=Decimal('120'),
                total_amount=Decimal('120'), status='confirmed')
            OrderItem.objects.create(
                order=order, product=test_product, item_type='product',
                product_name=test_product.name, product_weight='250g',
                quantity=1, price=Decimal('120'), final_price=Decimal('120'))
        # The post_save -> on_commit receiver should have logged a purchase event.
        assert UserEvent.objects.filter(
            user=test_user, event_type='purchase', product=test_product).exists()
