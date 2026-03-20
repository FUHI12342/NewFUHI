"""Sales analysis text generation service.

Generates analysis summaries, findings, recommendations, and scores
entirely locally — no external API calls. Uses DB data + statistical
computation + template-based text generation.
"""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Sum, F, Count, Avg
from django.db.models.functions import TruncDate, TruncWeek, ExtractHour, ExtractWeekDay
from django.utils import timezone

from booking.models import OrderItem

logger = logging.getLogger(__name__)

# Industry benchmarks
BENCHMARKS = {
    'growth_rate': {'good': 5.0, 'warn': 0.0},
    'star_ratio': {'good': 0.30, 'warn': 0.15},
    'abc_concentration': {'good': 0.70, 'warn': 0.50},
    'forecast_trend': {'good': 0.05, 'warn': -0.05},
    'peak_concentration': {'good': 0.30, 'warn': 0.50},
    'aov_growth': {'good': 3.0, 'warn': 0.0},
}


def _grade(metric_key, value):
    """Return letter grade A+ to D based on benchmark."""
    bench = BENCHMARKS.get(metric_key, {})
    good = bench.get('good', 0)
    warn = bench.get('warn', 0)
    if value >= good * 2:
        return 'A+'
    elif value >= good:
        return 'A'
    elif value >= (good + warn) / 2:
        return 'B+'
    elif value >= warn:
        return 'B'
    elif value >= warn * 0.5:
        return 'C'
    return 'D'


def _build_filters(scope, channel_filter, since):
    """Build combined filter kwargs."""
    filters = {'order__created_at__gte': since}
    filters.update(scope)
    if channel_filter:
        filters.update(channel_filter)
    return filters


class SalesAnalysisEngine:
    """Local analysis engine: DB → stats → text generation."""

    def analyze(self, analysis_type, store_scope, channel_filter):
        """Run analysis and return structured result.

        Returns:
            dict with 'summary', 'findings', 'recommendations', 'score'
        """
        handler = getattr(self, f'_analyze_{analysis_type}', None)
        if handler is None:
            return {
                'summary': '分析タイプが不明です',
                'findings': [],
                'recommendations': [],
                'score': '-',
            }
        return handler(store_scope, channel_filter)

    def _analyze_sales_trend(self, scope, ch_filter):
        now = timezone.now()
        since = now - timedelta(days=90)
        prev_since = since - timedelta(days=90)
        filters = _build_filters(scope, ch_filter, since)
        prev_filters = _build_filters(scope, ch_filter, prev_since)
        prev_filters['order__created_at__lt'] = since

        # Current period revenue
        current = (
            OrderItem.objects.filter(**filters)
            .aggregate(total=Sum(F('qty') * F('unit_price')))
        )
        current_total = current['total'] or 0

        # Previous period revenue
        prev = (
            OrderItem.objects.filter(**prev_filters)
            .aggregate(total=Sum(F('qty') * F('unit_price')))
        )
        prev_total = prev['total'] or 0

        # Weekly pattern
        weekly = (
            OrderItem.objects.filter(**filters)
            .annotate(weekday=ExtractWeekDay('order__created_at'))
            .values('weekday')
            .annotate(revenue=Sum(F('qty') * F('unit_price')))
        )
        weekday_rev = {w['weekday']: w['revenue'] or 0 for w in weekly}
        weekday_names = {1: '日', 2: '月', 3: '火', 4: '水', 5: '木', 6: '金', 7: '土'}

        growth_pct = ((current_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
        weekdays_avg = sum(weekday_rev.get(d, 0) for d in range(2, 7)) / 5 if weekday_rev else 0
        weekend_avg = sum(weekday_rev.get(d, 0) for d in [1, 7]) / 2 if weekday_rev else 0
        weekend_ratio = weekend_avg / weekdays_avg if weekdays_avg > 0 else 1.0

        peak_day = max(weekday_rev, key=weekday_rev.get) if weekday_rev else 6
        score = _grade('growth_rate', growth_pct)

        findings = [
            f'直近90日の総売上: ¥{current_total:,.0f}',
            f'前期比: {"+" if growth_pct >= 0 else ""}{growth_pct:.1f}%',
            f'週末は平日の{weekend_ratio:.1f}倍の売上',
            f'最も売上が高い曜日: {weekday_names.get(peak_day, "不明")}曜日',
        ]

        recommendations = []
        if growth_pct < 0:
            recommendations.append('売上が減少傾向です。プロモーション施策の検討をお勧めします')
        if weekend_ratio > 1.5:
            recommendations.append('平日の集客強化（ランチセット、平日限定クーポン等）が効果的です')
        if weekend_ratio < 1.0:
            recommendations.append('週末イベントの開催で売上アップが見込めます')
        recommendations.append('高単価メニューの訴求を強化して客単価向上を図りましょう')

        return {
            'summary': f'直近90日の売上は前期比{"+" if growth_pct >= 0 else ""}{growth_pct:.1f}%で{"成長" if growth_pct > 0 else "減少"}傾向。週末が平日の{weekend_ratio:.1f}倍。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }

    def _analyze_menu_engineering(self, scope, ch_filter):
        since = timezone.now() - timedelta(days=90)
        filters = _build_filters(scope, ch_filter, since)

        stats = list(
            OrderItem.objects.filter(**filters)
            .values('product_id', 'product__name', 'product__margin_rate')
            .annotate(
                qty_sold=Sum('qty'),
                revenue=Sum(F('qty') * F('unit_price')),
            )
            .order_by('-qty_sold')
        )

        if not stats:
            return {
                'summary': 'データ不足のため分析できません',
                'findings': [], 'recommendations': [], 'score': '-',
            }

        total_qty = sum(s['qty_sold'] or 0 for s in stats)
        total_margin = sum(s['product__margin_rate'] or 0 for s in stats)
        count = len(stats)
        avg_pop = total_qty / count if count else 0
        avg_margin = total_margin / count if count else 0

        quadrants = defaultdict(list)
        for s in stats:
            high_pop = (s['qty_sold'] or 0) >= avg_pop
            high_margin = (s['product__margin_rate'] or 0) >= avg_margin
            if high_pop and high_margin:
                quadrants['star'].append(s)
            elif high_pop:
                quadrants['plowhorse'].append(s)
            elif high_margin:
                quadrants['puzzle'].append(s)
            else:
                quadrants['dog'].append(s)

        star_count = len(quadrants['star'])
        dog_count = len(quadrants['dog'])
        star_revenue = sum(s['revenue'] or 0 for s in quadrants['star'])
        total_revenue = sum(s['revenue'] or 0 for s in stats)
        star_pct = star_revenue / total_revenue * 100 if total_revenue > 0 else 0

        score = _grade('star_ratio', star_count / count if count else 0)

        findings = [
            f'Star商品: {star_count}品（売上の{star_pct:.0f}%）',
            f'Dog商品: {dog_count}品',
            f'平均利益率: {avg_margin * 100:.1f}%',
            f'分析対象: {count}商品',
        ]

        recommendations = []
        if dog_count > 0:
            dog_names = [s['product__name'] for s in quadrants['dog'][:3]]
            recommendations.append(f'Dog商品（{", ".join(dog_names)}）はメニュー見直しを推奨')
        if quadrants['puzzle']:
            puzzle_names = [s['product__name'] for s in quadrants['puzzle'][:3]]
            recommendations.append(f'Puzzle商品（{", ".join(puzzle_names)}）は販促強化で Star化の可能性あり')
        if quadrants['plowhorse']:
            recommendations.append('Plowhorse商品は価格改定・高付加価値化で利益率改善を検討')

        return {
            'summary': f'Star商品が売上の{star_pct:.0f}%を占め{"健全" if star_pct > 40 else "改善余地あり"}。Dog{dog_count}品は見直し推奨。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }

    def _analyze_abc_analysis(self, scope, ch_filter):
        since = timezone.now() - timedelta(days=90)
        filters = _build_filters(scope, ch_filter, since)

        stats = list(
            OrderItem.objects.filter(**filters)
            .values('product_id', 'product__name')
            .annotate(revenue=Sum(F('qty') * F('unit_price')))
            .order_by('-revenue')
        )

        if not stats:
            return {
                'summary': 'データ不足のため分析できません',
                'findings': [], 'recommendations': [], 'score': '-',
            }

        total_revenue = sum(s['revenue'] or 0 for s in stats)
        cumulative = 0
        a_count = b_count = c_count = 0
        a_revenue = 0
        for s in stats:
            rev = s['revenue'] or 0
            cumulative += rev
            pct = cumulative / total_revenue if total_revenue > 0 else 0
            if pct <= 0.80:
                a_count += 1
                a_revenue += rev
            elif pct <= 0.95:
                b_count += 1
            else:
                c_count += 1

        concentration = a_revenue / total_revenue if total_revenue > 0 else 0
        score = _grade('abc_concentration', concentration)

        findings = [
            f'A群: {a_count}品（売上の{concentration * 100:.0f}%）',
            f'B群: {b_count}品',
            f'C群: {c_count}品（在庫コスト削減の候補）',
            f'総売上: ¥{total_revenue:,.0f}',
        ]

        recommendations = []
        if a_count <= 3:
            recommendations.append('売上がA群の少数商品に集中しています。メニュー多様化を検討してください')
        if c_count > 5:
            recommendations.append(f'C群{c_count}品は在庫コスト削減の候補です。販売終了を検討してください')
        recommendations.append('A群商品の安定供給を最優先で確保してください')

        return {
            'summary': f'上位{a_count}品でA群（売上{concentration * 100:.0f}%）を構成。C群{c_count}品は在庫コスト削減の候補。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }

    def _analyze_forecast(self, scope, ch_filter):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast(scope, forecast_days=14, channel_filter=ch_filter)
        historical = result.get('historical', [])
        forecast = result.get('forecast', [])

        if not forecast:
            return {
                'summary': 'データ不足のため予測できません',
                'findings': [], 'recommendations': [], 'score': '-',
            }

        avg_predicted = sum(f['predicted'] for f in forecast) / len(forecast) if forecast else 0
        last_hist = historical[-7:] if len(historical) >= 7 else historical
        avg_recent = sum(h['revenue'] for h in last_hist) / len(last_hist) if last_hist else 0
        trend_pct = ((avg_predicted - avg_recent) / avg_recent * 100) if avg_recent > 0 else 0

        confidence_range = 0
        if forecast:
            ranges = [(f['upper'] - f['lower']) / f['predicted'] * 100 for f in forecast if f['predicted'] > 0]
            confidence_range = sum(ranges) / len(ranges) if ranges else 0

        score = _grade('forecast_trend', trend_pct / 100)

        findings = [
            f'14日後の平均予測売上: ¥{avg_predicted:,.0f}/日',
            f'直近実績対比: {"+" if trend_pct >= 0 else ""}{trend_pct:.1f}%',
            f'予測信頼区間: ±{confidence_range:.0f}%',
            f'予測手法: {result.get("method", "moving_average")}',
        ]

        recommendations = []
        if trend_pct > 10:
            recommendations.append('上昇トレンドです。在庫を多めに確保してください')
        elif trend_pct < -10:
            recommendations.append('下降トレンドです。プロモーション施策を検討してください')
        recommendations.append('週末に向けた仕入れ量の調整を推奨します')

        return {
            'summary': f'14日後の売上予測: ¥{avg_predicted:,.0f}/日（±{confidence_range:.0f}%）。{"上昇" if trend_pct > 0 else "下降"}傾向。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }

    def _analyze_heatmap(self, scope, ch_filter):
        since = timezone.now() - timedelta(days=90)
        filters = _build_filters(scope, ch_filter, since)

        data = list(
            OrderItem.objects.filter(**filters)
            .annotate(
                weekday=ExtractWeekDay('order__created_at'),
                hour=ExtractHour('order__created_at'),
            )
            .values('weekday', 'hour')
            .annotate(revenue=Sum(F('qty') * F('unit_price')))
            .order_by('weekday', 'hour')
        )

        if not data:
            return {
                'summary': 'データ不足のため分析できません',
                'findings': [], 'recommendations': [], 'score': '-',
            }

        total_revenue = sum(d['revenue'] or 0 for d in data)
        hour_totals = defaultdict(int)
        for d in data:
            hour_totals[d['hour']] += d['revenue'] or 0

        # Find peak hours (top 3)
        sorted_hours = sorted(hour_totals.items(), key=lambda x: -x[1])
        peak_hours = sorted_hours[:3]
        dead_hours = sorted_hours[-3:] if len(sorted_hours) > 3 else []

        peak_pct = sum(h[1] for h in peak_hours) / total_revenue * 100 if total_revenue > 0 else 0
        concentration = peak_pct / 100
        score = _grade('peak_concentration', 1 - concentration)

        findings = [
            f'ピーク時間帯: {peak_hours[0][0]}時〜{peak_hours[-1][0] + 1}時（売上の{peak_pct:.0f}%）',
            f'最も売上が低い時間帯: {dead_hours[-1][0]}時台' if dead_hours else '',
            f'分析期間: 過去90日',
        ]
        findings = [f for f in findings if f]

        recommendations = []
        if dead_hours:
            dead_hour_range = f'{dead_hours[-1][0]}〜{dead_hours[0][0]}時'
            recommendations.append(f'{dead_hour_range}はスタッフ削減で人件費最適化が可能')
        if peak_pct > 50:
            recommendations.append('ピーク時間帯への集中が高いため、スタッフ配置を厚くしてください')
        recommendations.append('閑散時間帯限定のハッピーアワー施策で売上底上げを検討')

        return {
            'summary': f'{peak_hours[0][0]}〜{peak_hours[-1][0] + 1}時が売上の{peak_pct:.0f}%。閑散時間帯のスタッフ最適化が可能。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }

    def _analyze_aov(self, scope, ch_filter):
        now = timezone.now()
        since = now - timedelta(days=90)
        prev_since = since - timedelta(days=90)
        filters = _build_filters(scope, ch_filter, since)
        prev_filters = _build_filters(scope, ch_filter, prev_since)
        prev_filters['order__created_at__lt'] = since

        current = (
            OrderItem.objects.filter(**filters)
            .aggregate(
                total_revenue=Sum(F('qty') * F('unit_price')),
                order_count=Count('order_id', distinct=True),
            )
        )
        prev = (
            OrderItem.objects.filter(**prev_filters)
            .aggregate(
                total_revenue=Sum(F('qty') * F('unit_price')),
                order_count=Count('order_id', distinct=True),
            )
        )

        current_aov = (
            round((current['total_revenue'] or 0) / current['order_count'])
            if current['order_count']
            else 0
        )
        prev_aov = (
            round((prev['total_revenue'] or 0) / prev['order_count'])
            if prev['order_count']
            else 0
        )
        growth_pct = ((current_aov - prev_aov) / prev_aov * 100) if prev_aov > 0 else 0

        score = _grade('aov_growth', growth_pct)

        findings = [
            f'現在の客単価: ¥{current_aov:,}',
            f'前期比: {"+" if growth_pct >= 0 else ""}{growth_pct:.1f}%',
            f'注文数: {current["order_count"] or 0}件',
            f'総売上: ¥{(current["total_revenue"] or 0):,.0f}',
        ]

        recommendations = []
        if growth_pct < 0:
            recommendations.append('客単価が下降傾向です。セットメニューやアップセル施策を検討')
        recommendations.append('高単価メニューのおすすめ表示で客単価向上を図りましょう')
        recommendations.append('ドリンク+フードのセット割引で注文点数を増やす施策が効果的')

        return {
            'summary': f'客単価¥{current_aov:,}で前月比{"+" if growth_pct >= 0 else ""}{growth_pct:.1f}%。{"セットメニュー導入が効果的" if growth_pct < 3 else "良好な推移"}。',
            'findings': findings,
            'recommendations': recommendations,
            'score': score,
        }
