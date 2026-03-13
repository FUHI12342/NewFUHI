# booking/services/visitor_forecast.py
"""来客予測サービス — PIRセンサーデータ/VisitorCountから来客数を予測.

7日間移動平均 × 曜日係数で、今後7-14日の来客を予測する。
スタッフ推奨人数も合わせて返す。
"""
import logging
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Sum
from django.utils import timezone

from booking.models import VisitorCount

logger = logging.getLogger(__name__)

# 来客あたりスタッフ数の目安（調整可能）
DEFAULT_VISITORS_PER_STAFF = 15
MIN_STAFF = 1


def compute_visitor_forecast(scope=None, forecast_days=14, history_days=56):
    """来客予測を生成する.

    Args:
        scope: dict of filter kwargs for VisitorCount (e.g. {'store': store})
        forecast_days: 予測対象日数 (7-90)
        history_days: 参照する過去データ日数 (デフォルト56日=8週分)

    Returns:
        dict with 'historical', 'forecast', 'staff_recommendation' keys
    """
    if scope is None:
        scope = {}

    now = timezone.now()
    since = (now - timedelta(days=history_days)).date()

    # 日別来客数を集計
    daily_visitors = (
        VisitorCount.objects
        .filter(date__gte=since, **scope)
        .values('date')
        .annotate(total_visitors=Sum('estimated_visitors'))
        .order_by('date')
    )

    date_map = {}
    for row in daily_visitors:
        date_map[row['date']] = row['total_visitors'] or 0

    historical_list = [
        {'date': d.isoformat(), 'visitors': v}
        for d, v in sorted(date_map.items())
    ]

    # 曜日別に集計 (0=月曜..6=日曜)
    weekday_totals = defaultdict(float)
    weekday_counts = defaultdict(int)
    overall_total = 0
    overall_count = 0

    # 直近4週(28日)をベースラインとする
    today = now.date()
    baseline_start = today - timedelta(days=28)

    for d, visitors in date_map.items():
        if d >= baseline_start:
            dow = d.weekday()
            weekday_totals[dow] += visitors
            weekday_counts[dow] += 1
            overall_total += visitors
            overall_count += 1

    avg_daily = overall_total / overall_count if overall_count > 0 else 0

    # 曜日係数
    weekday_coef = {}
    for dow in range(7):
        if weekday_counts[dow] > 0 and avg_daily > 0:
            dow_avg = weekday_totals[dow] / weekday_counts[dow]
            weekday_coef[dow] = dow_avg / avg_daily
        else:
            weekday_coef[dow] = 1.0

    # 標準偏差ベースの信頼区間計算用データ
    weekday_values = defaultdict(list)
    for d, visitors in date_map.items():
        if d >= baseline_start:
            weekday_values[d.weekday()].append(visitors)

    def _std_dev(values):
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

    # 予測生成
    forecast = []
    staff_recommendation = []

    for i in range(1, forecast_days + 1):
        forecast_date = today + timedelta(days=i)
        dow = forecast_date.weekday()
        predicted = avg_daily * weekday_coef[dow]

        # 信頼区間: 曜日別の標準偏差ベース (なければ ±30%)
        dow_values = weekday_values.get(dow, [])
        if len(dow_values) >= 2:
            std = _std_dev(dow_values)
            lower = max(0, round(predicted - 1.96 * std))
            upper = round(predicted + 1.96 * std)
        else:
            lower = max(0, round(predicted * 0.7))
            upper = round(predicted * 1.3)

        predicted_rounded = round(predicted)
        forecast.append({
            'date': forecast_date.isoformat(),
            'weekday': dow,
            'predicted': predicted_rounded,
            'lower': lower,
            'upper': upper,
        })

        # スタッフ推奨
        recommended_staff = max(
            MIN_STAFF,
            -(-predicted_rounded // DEFAULT_VISITORS_PER_STAFF),  # 切り上げ除算
        ) if predicted_rounded > 0 else MIN_STAFF
        staff_recommendation.append({
            'date': forecast_date.isoformat(),
            'weekday': dow,
            'predicted_visitors': predicted_rounded,
            'recommended_staff': recommended_staff,
            'visitors_per_staff': DEFAULT_VISITORS_PER_STAFF,
        })

    return {
        'historical': historical_list,
        'forecast': forecast,
        'staff_recommendation': staff_recommendation,
        'method': 'weekday_moving_average',
        'baseline_days': min(28, overall_count),
    }
