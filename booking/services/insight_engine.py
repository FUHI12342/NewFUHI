# booking/services/insight_engine.py
"""Proactive business insight engine.

Detects anomalies and opportunities from store data:
- Sales drops (>20% below rolling avg)
- Low stock on A-rank items
- Staffing imbalances
- Menu performance shifts
- Customer retention drops
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Sum, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from booking.models import (
    BusinessInsight, Order, OrderItem, Product, Store,
    ShiftAssignment, Schedule,
)

logger = logging.getLogger(__name__)


def generate_insights(store=None):
    """Generate insights for a store (or all stores if None).

    Returns list of created BusinessInsight instances.
    """
    stores = [store] if store else Store.objects.all()
    created = []
    for s in stores:
        created.extend(_check_sales_drop(s))
        created.extend(_check_low_stock(s))
        created.extend(_check_staffing(s))
        created.extend(_check_reservation_cancellations(s))
    return created


def _check_sales_drop(store):
    """Detect if recent sales are significantly below rolling average."""
    now = timezone.now()
    recent_end = now
    recent_start = now - timedelta(days=7)
    baseline_start = now - timedelta(days=37)
    baseline_end = now - timedelta(days=7)

    scope = {'order__store': store}

    recent_rev = (
        OrderItem.objects
        .filter(order__created_at__gte=recent_start, order__created_at__lt=recent_end, **scope)
        .aggregate(total=Sum(F('qty') * F('unit_price')))
    )['total'] or 0

    baseline_rev = (
        OrderItem.objects
        .filter(order__created_at__gte=baseline_start, order__created_at__lt=baseline_end, **scope)
        .aggregate(total=Sum(F('qty') * F('unit_price')))
    )['total'] or 0

    # Normalize to weekly
    baseline_weekly = baseline_rev / 4.0 if baseline_rev > 0 else 0

    if baseline_weekly > 0 and recent_rev < baseline_weekly * 0.8:
        drop_pct = round((1 - recent_rev / baseline_weekly) * 100, 1)
        insight = BusinessInsight.objects.create(
            store=store,
            category='sales',
            severity='warning' if drop_pct < 30 else 'critical',
            title=f'売上が前月比 {drop_pct}% 減少',
            message=f'直近7日間の売上（{recent_rev:,}円）が過去30日平均（週{int(baseline_weekly):,}円）を{drop_pct}%下回っています。',
            data={
                'recent_revenue': recent_rev,
                'baseline_weekly': round(baseline_weekly),
                'drop_pct': drop_pct,
            },
        )
        return [insight]
    return []


def _check_low_stock(store):
    """Detect A-rank items with dangerously low stock."""
    low_items = Product.objects.filter(
        store=store,
        is_active=True,
        stock__lte=F('low_stock_threshold'),
    ).order_by('stock')[:10]

    insights = []
    for item in low_items:
        if item.stock <= 0:
            severity = 'critical'
            title = f'在庫切れ: {item.name}'
        else:
            severity = 'warning'
            title = f'在庫低下: {item.name} (残{item.stock})'

        insight = BusinessInsight.objects.create(
            store=store,
            category='inventory',
            severity=severity,
            title=title,
            message=f'{item.name}の在庫が閾値({item.low_stock_threshold})を下回っています。残り{item.stock}個。',
            data={
                'product_id': item.id,
                'product_name': item.name,
                'stock': item.stock,
                'threshold': item.low_stock_threshold,
            },
        )
        insights.append(insight)
    return insights


def _check_staffing(store):
    """Detect potential understaffing based on reservations vs assignments."""
    now = timezone.now()
    next_week = now + timedelta(days=7)

    reservation_count = Schedule.objects.filter(
        staff__store=store,
        start__gte=now,
        start__lt=next_week,
        is_cancelled=False,
        is_temporary=False,
    ).count()

    shift_count = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=now.date(),
        date__lt=next_week.date(),
    ).count()

    if reservation_count > 0 and shift_count > 0:
        ratio = reservation_count / shift_count
        if ratio > 5:
            insight = BusinessInsight.objects.create(
                store=store,
                category='staffing',
                severity='warning',
                title='来週の予約に対してスタッフ不足の可能性',
                message=f'来週の予約{reservation_count}件に対してシフト{shift_count}枠。1シフトあたり{ratio:.1f}件の予約があります。',
                data={
                    'reservations': reservation_count,
                    'shifts': shift_count,
                    'ratio': round(ratio, 1),
                },
            )
            return [insight]
    return []


def _check_reservation_cancellations(store):
    """Detect high cancellation rate."""
    now = timezone.now()
    since = now - timedelta(days=14)

    total = Schedule.objects.filter(
        staff__store=store, start__gte=since,
    ).count()
    cancelled = Schedule.objects.filter(
        staff__store=store, start__gte=since, is_cancelled=True,
    ).count()

    if total >= 10:
        rate = cancelled / total
        if rate > 0.2:
            insight = BusinessInsight.objects.create(
                store=store,
                category='customer',
                severity='warning',
                title=f'キャンセル率が{round(rate*100)}%に上昇',
                message=f'直近14日間で{total}件中{cancelled}件がキャンセル（{round(rate*100)}%）。',
                data={
                    'total': total,
                    'cancelled': cancelled,
                    'rate': round(rate, 4),
                },
            )
            return [insight]
    return []
