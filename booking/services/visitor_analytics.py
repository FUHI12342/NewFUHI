"""来客分析サービス - PIRセンサーデータから来客数を推定"""
import logging
from datetime import date, timedelta
from collections import defaultdict

from django.db.models import Count, Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def aggregate_visitor_counts(store, date_from, date_to):
    """IoTEvent(pir_triggered) → VisitorCount 集計

    session_gap_seconds 内の連続検知は同一来客とカウント。

    Returns:
        int: 作成/更新したVisitorCountレコード数
    """
    from booking.models import IoTEvent, VisitorCount, VisitorAnalyticsConfig, Order

    # 店舗設定取得
    try:
        config = store.visitor_config
        session_gap = config.session_gap_seconds
        pir_device = config.pir_device
    except VisitorAnalyticsConfig.DoesNotExist:
        session_gap = 300
        pir_device = None

    # PIRデバイス特定
    if pir_device:
        device_filter = Q(device=pir_device)
    else:
        device_filter = Q(device__store=store)

    count = 0
    current_date = date_from
    while current_date <= date_to:
        for hour in range(24):
            hour_start = timezone.make_aware(
                timezone.datetime(current_date.year, current_date.month, current_date.day, hour, 0, 0)
            )
            hour_end = hour_start + timedelta(hours=1)

            # PIRイベント取得
            pir_events = IoTEvent.objects.filter(
                device_filter,
                pir_triggered=True,
                created_at__gte=hour_start,
                created_at__lt=hour_end,
            ).order_by('created_at').values_list('created_at', flat=True)

            pir_count = len(pir_events)

            # セッション分割で来客数推定
            estimated = _count_sessions(list(pir_events), session_gap)

            # 注文数カウント
            order_count = Order.objects.filter(
                store=store,
                created_at__gte=hour_start,
                created_at__lt=hour_end,
            ).count()

            if pir_count > 0 or order_count > 0:
                VisitorCount.objects.update_or_create(
                    store=store,
                    date=current_date,
                    hour=hour,
                    defaults={
                        'pir_count': pir_count,
                        'estimated_visitors': estimated,
                        'order_count': order_count,
                    },
                )
                count += 1

        current_date += timedelta(days=1)

    logger.info(
        "Aggregated %d visitor count records for %s (%s ~ %s)",
        count, store.name, date_from, date_to,
    )
    return count


def _count_sessions(timestamps, gap_seconds):
    """タイムスタンプリストをセッションに分割して来客数を推定"""
    if not timestamps:
        return 0

    sessions = 1
    for i in range(1, len(timestamps)):
        diff = (timestamps[i] - timestamps[i - 1]).total_seconds()
        if diff > gap_seconds:
            sessions += 1
    return sessions


def calculate_conversion_rate(store, date_from, date_to):
    """来客数→注文数コンバージョン率を計算"""
    from booking.models import VisitorCount
    from django.db.models import Sum

    totals = VisitorCount.objects.filter(
        store=store,
        date__gte=date_from,
        date__lte=date_to,
    ).aggregate(
        total_visitors=Sum('estimated_visitors'),
        total_orders=Sum('order_count'),
    )

    visitors = totals['total_visitors'] or 0
    orders = totals['total_orders'] or 0

    if visitors == 0:
        return {
            'total_visitors': 0,
            'total_orders': orders,
            'conversion_rate': 0.0,
        }

    return {
        'total_visitors': visitors,
        'total_orders': orders,
        'conversion_rate': round((orders / visitors) * 100, 1),
    }


def get_heatmap_data(store, weeks=4):
    """曜日×時間のヒートマップデータを生成"""
    from booking.models import VisitorCount
    from django.db.models import Avg

    date_from = date.today() - timedelta(weeks=weeks)

    # 曜日(0=月)×時間(0-23)の平均来客数
    records = VisitorCount.objects.filter(
        store=store,
        date__gte=date_from,
    ).values('hour').annotate(
        avg_visitors=Avg('estimated_visitors'),
    )

    # 曜日別にも集計
    heatmap = defaultdict(lambda: defaultdict(float))

    day_records = VisitorCount.objects.filter(
        store=store,
        date__gte=date_from,
    )

    for record in day_records:
        weekday = record.date.weekday()  # 0=Monday
        heatmap[weekday][record.hour] += record.estimated_visitors

    # 週数で割って平均化
    result = {}
    for weekday in range(7):
        result[weekday] = {}
        for hour in range(24):
            avg = heatmap[weekday].get(hour, 0) / max(weeks, 1)
            result[weekday][hour] = round(avg, 1)

    return result
