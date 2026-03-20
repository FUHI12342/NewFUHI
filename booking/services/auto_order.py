# booking/services/auto_order.py
"""自動発注推奨サービス — 商品ごとの消費ペースと在庫から発注推奨を算出.

日次消費率 = 過去N日間の出庫数(OrderItem.qty合計) / N
残日数 = 現在庫 / 日次消費率
推奨発注数 = (リードタイム + 安全バッファ) × 日次消費率 - 現在庫
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum, F
from django.utils import timezone

from booking.models import Product, OrderItem

logger = logging.getLogger(__name__)

# デフォルト設定
DEFAULT_LEAD_TIME_DAYS = 1    # 仕入れリードタイム
DEFAULT_SAFETY_BUFFER_DAYS = 1  # 安全バッファ日数
DEFAULT_HISTORY_DAYS = 30     # 消費率計算の参照日数
DEFAULT_ORDER_CYCLE_DAYS = 7  # 発注サイクル日数


def compute_auto_order(scope=None, history_days=None, lead_time_days=None, safety_buffer_days=None):
    """自動発注推奨リストを生成する.

    Args:
        scope: dict of filter kwargs for Product store scoping (e.g. {'store': store})
        history_days: 消費率を計算する過去日数
        lead_time_days: 仕入れリードタイム (日)
        safety_buffer_days: 安全バッファ (日)

    Returns:
        dict with 'recommendations', 'summary' keys
    """
    if scope is None:
        scope = {}
    if history_days is None:
        history_days = DEFAULT_HISTORY_DAYS
    if lead_time_days is None:
        lead_time_days = DEFAULT_LEAD_TIME_DAYS
    if safety_buffer_days is None:
        safety_buffer_days = DEFAULT_SAFETY_BUFFER_DAYS

    now = timezone.now()
    since = now - timedelta(days=history_days)

    # 対象商品取得（アクティブのみ）
    products = Product.objects.filter(is_active=True, **scope)

    # OrderItem scope の変換 (store → order__store)
    order_item_scope = {f'order__{k}': v for k, v in scope.items()}

    # 商品別消費量を集計
    consumption = (
        OrderItem.objects
        .filter(order__created_at__gte=since, **order_item_scope)
        .values('product_id')
        .annotate(total_qty=Sum('qty'))
    )
    consumption_map = {
        c['product_id']: c['total_qty'] or 0
        for c in consumption
    }

    # 直近7日の消費量（短期トレンド検出用）
    recent_since = now - timedelta(days=7)
    recent_consumption = (
        OrderItem.objects
        .filter(order__created_at__gte=recent_since, **order_item_scope)
        .values('product_id')
        .annotate(total_qty=Sum('qty'))
    )
    recent_consumption_map = {
        c['product_id']: c['total_qty'] or 0
        for c in recent_consumption
    }

    recommendations = []
    summary = {
        'total_products': 0,
        'critical_count': 0,
        'warning_count': 0,
        'ok_count': 0,
    }

    for product in products:
        total_consumed = consumption_map.get(product.id, 0)

        # 日次消費率（直近7日と全期間の加重平均で精度向上）
        daily_consumption = total_consumed / history_days if history_days > 0 else 0

        # 直近7日の消費率で短期トレンドを加味
        recent_consumed = recent_consumption_map.get(product.id, 0)
        recent_daily = recent_consumed / min(7, history_days) if history_days > 0 else 0
        # 加重平均: 直近60% + 全期間40%
        if recent_daily > 0 and daily_consumption > 0:
            daily_consumption = recent_daily * 0.6 + daily_consumption * 0.4

        # 残日数（在庫がゼロ以下の場合は0）
        if daily_consumption > 0:
            days_remaining = product.stock / daily_consumption
        elif product.stock > 0:
            days_remaining = 999  # 消費がなければ在庫は減らない
        else:
            days_remaining = 0

        # lead_time_days フィールドがProductに存在するか確認
        product_lead_time = getattr(product, 'lead_time_days', lead_time_days)

        # 緊急度の判定
        reorder_point = product_lead_time + safety_buffer_days
        if days_remaining <= product_lead_time:
            urgency = 'critical'
            summary['critical_count'] += 1
        elif days_remaining <= reorder_point:
            urgency = 'warning'
            summary['warning_count'] += 1
        else:
            urgency = 'ok'
            summary['ok_count'] += 1

        # 推奨発注数: (リードタイム + 安全バッファ + 発注サイクル) × 日次消費率 - 現在庫
        target_stock_days = product_lead_time + safety_buffer_days + DEFAULT_ORDER_CYCLE_DAYS
        recommended_qty = max(
            0,
            round(daily_consumption * target_stock_days - product.stock),
        )

        summary['total_products'] += 1

        recommendations.append({
            'product': {
                'id': product.id,
                'sku': product.sku,
                'name': product.name,
                'price': product.price,
            },
            'current_stock': product.stock,
            'low_stock_threshold': product.low_stock_threshold,
            'daily_consumption': round(daily_consumption, 2),
            'total_consumed_period': total_consumed,
            'days_remaining': round(days_remaining, 1) if days_remaining < 999 else None,
            'lead_time_days': product_lead_time,
            'recommended_qty': recommended_qty,
            'urgency': urgency,
        })

    # urgencyの優先度順にソート (critical > warning > ok)、同じ urgency 内では残日数昇順
    urgency_order = {'critical': 0, 'warning': 1, 'ok': 2}
    recommendations.sort(key=lambda r: (
        urgency_order.get(r['urgency'], 9),
        r['days_remaining'] if r['days_remaining'] is not None else 9999,
    ))

    return {
        'recommendations': recommendations,
        'summary': summary,
        'params': {
            'history_days': history_days,
            'lead_time_days': lead_time_days,
            'safety_buffer_days': safety_buffer_days,
        },
    }
