# booking/services/rfm_analysis.py
"""RFM (Recency, Frequency, Monetary) analysis service."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum, Max, F
from django.utils import timezone

from booking.models import Order, OrderItem

logger = logging.getLogger(__name__)


def compute_rfm(scope=None, days=365):
    """Compute RFM scores for all customers.

    Args:
        scope: dict of filter kwargs for OrderItem (e.g. {'order__store': store})
        days: lookback period in days

    Returns:
        list of dicts with customer_id, recency, frequency, monetary,
        r_score, f_score, m_score, rfm_score, segment
    """
    if scope is None:
        scope = {}
    now = timezone.now()
    since = now - timedelta(days=days)

    # Aggregate per customer
    customers = (
        Order.objects
        .filter(
            created_at__gte=since,
            customer_line_user_hash__isnull=False,
            **{k.replace('order__', ''): v for k, v in scope.items()},
        )
        .exclude(customer_line_user_hash='')
        .values('customer_line_user_hash')
        .annotate(
            last_order=Max('created_at'),
            frequency=Count('id'),
            monetary=Sum('items__qty') * 1,  # placeholder, computed below
        )
    )

    # Need to compute monetary from OrderItems properly
    # Re-aggregate with correct monetary
    customer_monetary = (
        OrderItem.objects
        .filter(
            order__created_at__gte=since,
            order__customer_line_user_hash__isnull=False,
            **scope,
        )
        .exclude(order__customer_line_user_hash='')
        .values('order__customer_line_user_hash')
        .annotate(
            total_spend=Sum(F('qty') * F('unit_price')),
        )
    )
    monetary_map = {
        c['order__customer_line_user_hash']: c['total_spend'] or 0
        for c in customer_monetary
    }

    customer_data = (
        Order.objects
        .filter(
            created_at__gte=since,
            customer_line_user_hash__isnull=False,
            **{k.replace('order__', ''): v for k, v in scope.items()},
        )
        .exclude(customer_line_user_hash='')
        .values('customer_line_user_hash')
        .annotate(
            last_order=Max('created_at'),
            frequency=Count('id'),
        )
    )

    if not customer_data:
        return []

    # Build raw RFM values
    rfm_raw = []
    for c in customer_data:
        cid = c['customer_line_user_hash']
        recency_days = (now - c['last_order']).days
        rfm_raw.append({
            'customer_id': cid,
            'recency': recency_days,
            'frequency': c['frequency'],
            'monetary': monetary_map.get(cid, 0),
        })

    if not rfm_raw:
        return []

    # Compute quintile-based scores (1-5)
    for metric in ['recency', 'frequency', 'monetary']:
        values = sorted(set(r[metric] for r in rfm_raw))
        n = len(values)
        if n == 0:
            continue

        # For recency: lower is better (score 5)
        # For frequency/monetary: higher is better (score 5)
        reverse = metric == 'recency'

        # Assign scores using percentile ranking
        for r in rfm_raw:
            val = r[metric]
            if n <= 5:
                # Few unique values: rank directly
                rank = values.index(val)
                if reverse:
                    score = 5 - int(rank * 5 / max(n, 1))
                else:
                    score = 1 + int(rank * 4 / max(n - 1, 1))
            else:
                # Percentile-based
                rank = values.index(val)
                pct = rank / (n - 1) if n > 1 else 0
                if reverse:
                    score = 5 - int(pct * 4)
                else:
                    score = 1 + int(pct * 4)
            r[f'{metric[0]}_score'] = max(1, min(5, score))

    # Classify segments
    for r in rfm_raw:
        rs = r.get('r_score', 3)
        fs = r.get('f_score', 3)
        ms = r.get('m_score', 3)
        r['rfm_score'] = rs * 100 + fs * 10 + ms
        r['segment'] = _classify_segment(rs, fs, ms)

    return rfm_raw


def _classify_segment(r, f, m):
    """Classify customer into RFM segment."""
    avg = (r + f + m) / 3

    if r >= 4 and f >= 4 and m >= 4:
        return 'champion'
    elif r >= 4 and f >= 3:
        return 'loyal'
    elif r >= 4 and f <= 2:
        return 'new'
    elif r >= 3 and f >= 3:
        return 'potential'
    elif r <= 2 and f >= 3:
        return 'at_risk'
    elif r <= 2 and f <= 2 and m >= 3:
        return 'cant_lose'
    elif r <= 2:
        return 'lost'
    else:
        return 'other'
