# booking/services/clv_analysis.py
"""CLV (Customer Lifetime Value) 顧客生涯価値分析サービス.

顧客セグメントごとのCLVを計算する:
  CLV = avg_order_value x monthly_frequency x avg_lifespan_months

識別子: customer_line_user_hash, customer_email, line_user_hash (Schedule) のいずれか
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum, Max, Min, F, Avg
from django.utils import timezone

from booking.models import Order, OrderItem

logger = logging.getLogger(__name__)

# セグメント閾値 (CLVパーセンタイル)
SEGMENT_HIGH_PCT = 0.70       # 上位30%
SEGMENT_MEDIUM_PCT = 0.40     # 中位30%
SEGMENT_AT_RISK_DAYS = 60     # 最終注文からこの日数以上 → at_risk
SEGMENT_LOST_DAYS = 120       # 最終注文からこの日数以上 → lost


def compute_clv(scope=None, months=6):
    """顧客セグメント別CLVを計算する.

    Args:
        scope: dict of filter kwargs for OrderItem (e.g. {'order__store': store})
        months: 分析対象の月数

    Returns:
        dict with 'segments', 'summary', 'customers' keys
    """
    if scope is None:
        scope = {}
    now = timezone.now()
    since = now - timedelta(days=months * 30)

    # 顧客別注文データの集約（OrderItem から revenue を計算）
    order_scope = {k.replace('order__', ''): v for k, v in scope.items()}

    customer_orders = (
        Order.objects
        .filter(
            created_at__gte=since,
            customer_line_user_hash__isnull=False,
            **order_scope,
        )
        .exclude(customer_line_user_hash='')
        .values('customer_line_user_hash')
        .annotate(
            order_count=Count('id'),
            first_order=Min('created_at'),
            last_order=Max('created_at'),
        )
    )

    # 顧客別の売上金額
    customer_revenue = (
        OrderItem.objects
        .filter(
            order__created_at__gte=since,
            order__customer_line_user_hash__isnull=False,
            **scope,
        )
        .exclude(order__customer_line_user_hash='')
        .values('order__customer_line_user_hash')
        .annotate(
            total_revenue=Sum(F('qty') * F('unit_price')),
        )
    )
    revenue_map = {
        c['order__customer_line_user_hash']: c['total_revenue'] or 0
        for c in customer_revenue
    }

    if not customer_orders:
        return {
            'segments': [],
            'summary': {
                'total_customers': 0,
                'avg_clv': 0,
                'total_revenue': 0,
                'avg_order_value': 0,
                'avg_frequency': 0,
            },
            'customers': [],
        }

    # 顧客ごとのCLV計算
    customer_data = []
    for c in customer_orders:
        cid = c['customer_line_user_hash']
        order_count = c['order_count']
        total_revenue = revenue_map.get(cid, 0)
        first_order = c['first_order']
        last_order = c['last_order']

        # 平均注文金額
        avg_order_value = total_revenue / order_count if order_count > 0 else 0

        # アクティブ期間（月数）
        if first_order and last_order:
            active_days = max((last_order - first_order).days, 1)
            active_months = active_days / 30.0
        else:
            active_months = 1.0

        # 月間頻度
        monthly_frequency = order_count / max(active_months, 1.0)

        # 予測ライフスパン（簡易: アクティブ期間の1.5倍、最低1ヶ月）
        estimated_lifespan = max(active_months * 1.5, 1.0)

        # CLV = avg_order_value x monthly_frequency x avg_lifespan_months
        clv = avg_order_value * monthly_frequency * estimated_lifespan

        # 直近注文からの日数
        days_since_last = (now - last_order).days if last_order else 999

        customer_data.append({
            'customer_id': cid[:12] + '...',  # ハッシュの一部のみ表示
            'order_count': order_count,
            'total_revenue': round(total_revenue),
            'avg_order_value': round(avg_order_value),
            'monthly_frequency': round(monthly_frequency, 2),
            'active_months': round(active_months, 1),
            'estimated_lifespan': round(estimated_lifespan, 1),
            'clv': round(clv),
            'days_since_last_order': days_since_last,
        })

    if not customer_data:
        return {
            'segments': [],
            'summary': {
                'total_customers': 0,
                'avg_clv': 0,
                'total_revenue': 0,
                'avg_order_value': 0,
                'avg_frequency': 0,
            },
            'customers': [],
        }

    # CLV降順ソート
    customer_data.sort(key=lambda x: -x['clv'])

    # セグメント分け
    clv_values = [c['clv'] for c in customer_data]
    total_customers = len(customer_data)

    # パーセンタイル閾値
    sorted_clvs = sorted(clv_values, reverse=True)
    high_threshold = sorted_clvs[int(total_customers * (1 - SEGMENT_HIGH_PCT))] if total_customers > 2 else 0
    medium_threshold = sorted_clvs[int(total_customers * (1 - SEGMENT_MEDIUM_PCT))] if total_customers > 2 else 0

    for c in customer_data:
        days = c['days_since_last_order']
        clv = c['clv']

        if days >= SEGMENT_LOST_DAYS:
            c['segment'] = 'lost'
        elif days >= SEGMENT_AT_RISK_DAYS:
            c['segment'] = 'at_risk'
        elif clv >= high_threshold:
            c['segment'] = 'high_value'
        elif clv >= medium_threshold:
            c['segment'] = 'medium_value'
        else:
            c['segment'] = 'low_value'

    # セグメント集計
    segment_stats = defaultdict(lambda: {'count': 0, 'total_clv': 0, 'total_revenue': 0})
    for c in customer_data:
        seg = c['segment']
        segment_stats[seg]['count'] += 1
        segment_stats[seg]['total_clv'] += c['clv']
        segment_stats[seg]['total_revenue'] += c['total_revenue']

    segments = []
    segment_order = ['high_value', 'medium_value', 'low_value', 'at_risk', 'lost']
    segment_labels = {
        'high_value': '高価値顧客',
        'medium_value': '中価値顧客',
        'low_value': '低価値顧客',
        'at_risk': '離脱リスク顧客',
        'lost': '離脱顧客',
    }
    for seg in segment_order:
        stats = segment_stats.get(seg)
        if stats and stats['count'] > 0:
            segments.append({
                'segment': seg,
                'label': segment_labels.get(seg, seg),
                'count': stats['count'],
                'pct': round(stats['count'] / total_customers * 100, 1),
                'avg_clv': round(stats['total_clv'] / stats['count']),
                'total_revenue': round(stats['total_revenue']),
            })

    # サマリー
    total_revenue = sum(c['total_revenue'] for c in customer_data)
    avg_clv = sum(c['clv'] for c in customer_data) / total_customers if total_customers > 0 else 0
    avg_order_value = sum(c['avg_order_value'] for c in customer_data) / total_customers if total_customers > 0 else 0
    avg_frequency = sum(c['monthly_frequency'] for c in customer_data) / total_customers if total_customers > 0 else 0

    return {
        'segments': segments,
        'summary': {
            'total_customers': total_customers,
            'avg_clv': round(avg_clv),
            'total_revenue': round(total_revenue),
            'avg_order_value': round(avg_order_value),
            'avg_frequency': round(avg_frequency, 2),
        },
        'customers': customer_data[:100],  # 上位100顧客のみ返す
    }
