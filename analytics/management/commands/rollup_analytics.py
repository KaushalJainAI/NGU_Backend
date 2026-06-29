"""
Recompute the analytics rollup tables from source signals.

Idempotent by design: for each target date it deletes that day's rollup rows
and recomputes them, so it is safe to run as often as you like (e.g. every few
minutes for "today" plus a nightly full pass). It also drains the anonymous
Redis counters into DailyAnonStat.

Usage:
    python manage.py rollup_analytics                 # yesterday + today
    python manage.py rollup_analytics --date 2026-06-20
    python manage.py rollup_analytics --days 30       # backfill last 30 days
"""
from datetime import date as date_cls, datetime, time, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Min, Sum
from django.utils import timezone

from analytics.anon import flush_anon_to_db
from analytics.models import (
    DailyFunnelRollup, DailySalesRollup, SearchTermStat, UserEvent,
)
from orders.models import Order, OrderItem

# Orders in these statuses are excluded from sales KPIs (not realised revenue).
EXCLUDED_ORDER_STATUSES = ['cancelled']


class Command(BaseCommand):
    help = "Recompute analytics rollup tables (sales, funnel, search) for given dates."

    def add_arguments(self, parser):
        parser.add_argument('--date', help='Single date to roll up (YYYY-MM-DD).')
        parser.add_argument('--days', type=int,
                            help='Backfill: roll up the last N days (inclusive of today).')

    def handle(self, *args, **options):
        dates = self._target_dates(options)
        for day in dates:
            with transaction.atomic():
                sales = self._rollup_sales(day)
                funnel = self._rollup_funnel(day)
                search = self._rollup_search(day)
            flushed = flush_anon_to_db(day)
            self.stdout.write(
                f"{day}: sales(orders={sales['orders']}, revenue={sales['revenue']}) "
                f"funnel={funnel} search_terms={search} anon_counters={flushed}"
            )
        self.stdout.write(self.style.SUCCESS(f"Rolled up {len(dates)} day(s)."))

    # -- date selection ------------------------------------------------------

    def _target_dates(self, options):
        today = timezone.localdate()
        if options.get('date'):
            try:
                return [date_cls.fromisoformat(options['date'])]
            except ValueError:
                raise CommandError("--date must be YYYY-MM-DD")
        if options.get('days'):
            n = options['days']
            return [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
        # Default: yesterday (now final) + today (partial).
        return [today - timedelta(days=1), today]

    def _day_range(self, day):
        """Timezone-aware [start, end) bounds for a local calendar day."""
        tz = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(day, time.min), tz)
        end = start + timedelta(days=1)
        return start, end

    # -- rollups -------------------------------------------------------------

    def _rollup_sales(self, day):
        start, end = self._day_range(day)
        orders_qs = (
            Order.objects
            .filter(created_at__gte=start, created_at__lt=end)
            .exclude(status__in=EXCLUDED_ORDER_STATUSES)
        )

        agg = orders_qs.aggregate(
            orders=Count('id'),
            revenue=Sum('total_amount'),
            coupon_discount=Sum('discount_amount'),
        )
        orders_count = agg['orders'] or 0
        revenue = agg['revenue'] or 0
        coupon_discount = agg['coupon_discount'] or 0

        units = (
            OrderItem.objects
            .filter(order__in=orders_qs)
            .aggregate(u=Sum('quantity'))['u'] or 0
        )
        coupon_orders = orders_qs.filter(coupon__isnull=False).count()
        aov = (revenue / orders_count) if orders_count else 0

        # New vs returning: a customer is "new" on the day their *first ever*
        # (non-excluded) order falls. Everyone else who ordered today is returning.
        buyer_ids = list(orders_qs.values_list('user_id', flat=True).distinct())
        new_customers = 0
        if buyer_ids:
            first_order = (
                Order.objects
                .exclude(status__in=EXCLUDED_ORDER_STATUSES)
                .filter(user_id__in=buyer_ids)
                .values('user_id')
                .annotate(first=Min('created_at'))
            )
            new_customers = sum(1 for r in first_order if start <= r['first'] < end)
        returning_customers = max(len(buyer_ids) - new_customers, 0)

        DailySalesRollup.objects.update_or_create(
            date=day,
            defaults={
                'orders': orders_count,
                'units': units,
                'revenue': revenue,
                'aov': aov,
                'coupon_orders': coupon_orders,
                'coupon_discount': coupon_discount,
                'new_customers': new_customers,
                'returning_customers': returning_customers,
            },
        )
        return {'orders': orders_count, 'revenue': revenue}

    def _rollup_funnel(self, day):
        start, end = self._day_range(day)
        DailyFunnelRollup.objects.filter(date=day).delete()
        rows = (
            UserEvent.objects
            .filter(created_at__gte=start, created_at__lt=end)
            .values('event_type')
            .annotate(c=Count('id'))
        )
        objs = [
            DailyFunnelRollup(date=day, event_type=r['event_type'], count=r['c'])
            for r in rows
        ]
        DailyFunnelRollup.objects.bulk_create(objs)
        return len(objs)

    def _rollup_search(self, day):
        start, end = self._day_range(day)
        SearchTermStat.objects.filter(date=day).delete()
        events = (
            UserEvent.objects
            .filter(event_type='search', created_at__gte=start, created_at__lt=end)
            .values_list('query', 'metadata')
        )
        # Aggregate in Python so we can read zero-result from the JSON metadata.
        agg = {}
        for query, metadata in events:
            term = (query or '').strip().lower()
            if not term:
                continue
            meta = metadata or {}
            zero = bool(meta.get('zero')) or meta.get('result_count') == 0
            entry = agg.setdefault(term, {'count': 0, 'zero': False})
            entry['count'] += 1
            # A term is flagged zero-result if any of its occurrences had none.
            entry['zero'] = entry['zero'] or zero
        objs = [
            SearchTermStat(date=day, term=term, count=v['count'], zero_result=v['zero'])
            for term, v in agg.items()
        ]
        SearchTermStat.objects.bulk_create(objs)
        return len(objs)
