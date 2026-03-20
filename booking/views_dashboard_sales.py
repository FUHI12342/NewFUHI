# booking/views_dashboard_sales.py
"""Dashboard sales-related API views: Sales, MenuEng, ABC, Forecast, Heatmap, AOV, Channel."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum, Q, F
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import OrderItem, SiteSettings
from .views_dashboard_base import (
    DashboardAuthMixin, PERIOD_TRUNC_MAP,
    _get_since_for_period, _parse_channel_filter, _clamp_int,
)

logger = logging.getLogger(__name__)


class SalesStatsAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/sales/?period=daily — sales statistics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        period = request.GET.get('period', 'daily')
        trunc_fn = PERIOD_TRUNC_MAP.get(period, PERIOD_TRUNC_MAP['daily'])
        scope = self.build_scope(store, 'order__store')
        since = _get_since_for_period(period)
        channel_filter = _parse_channel_filter(request)

        trend = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .annotate(date=trunc_fn('order__created_at'))
            .values('date')
            .annotate(total=Sum(F('qty') * F('unit_price')))
            .order_by('date')
        )
        trend_list = [{'date': t['date'].isoformat(), 'total': t['total'] or 0} for t in trend]

        top_products = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .values('product__name')
            .annotate(total=Sum('qty'))
            .order_by('-total')[:10]
        )
        products_list = [{'name': p['product__name'], 'total': p['total']} for p in top_products]

        return Response({'trend': trend_list, 'top_products': products_list})


class MenuEngineeringAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/menu-engineering/ — menu engineering matrix."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)
        scope = self.build_scope(store, 'order__store')
        channel_filter = _parse_channel_filter(request)

        product_stats = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .values('product_id', 'product__name', 'product__price', 'product__margin_rate')
            .annotate(
                qty_sold=Sum('qty'),
                revenue=Sum(F('qty') * F('unit_price')),
            )
            .order_by('-qty_sold')
        )

        if not product_stats:
            return Response({'products': [], 'avg_popularity': 0, 'avg_margin': 0})

        items = []
        total_qty = 0
        total_margin = 0
        count = 0
        for ps in product_stats:
            margin = ps['product__margin_rate'] or 0.0
            qty = ps['qty_sold'] or 0
            items.append({
                'id': ps['product_id'],
                'name': ps['product__name'],
                'price': ps['product__price'],
                'qty_sold': qty,
                'revenue': ps['revenue'] or 0,
                'margin_rate': round(margin, 3),
            })
            total_qty += qty
            total_margin += margin
            count += 1

        avg_popularity = total_qty / count if count else 0
        avg_margin = total_margin / count if count else 0

        for item in items:
            high_pop = item['qty_sold'] >= avg_popularity
            high_margin = item['margin_rate'] >= avg_margin
            if high_pop and high_margin:
                item['quadrant'] = 'star'
            elif high_pop and not high_margin:
                item['quadrant'] = 'plowhorse'
            elif not high_pop and high_margin:
                item['quadrant'] = 'puzzle'
            else:
                item['quadrant'] = 'dog'

        return Response({
            'products': items,
            'avg_popularity': round(avg_popularity, 1),
            'avg_margin': round(avg_margin, 3),
        })


class ABCAnalysisAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/abc-analysis/ — ABC (Pareto) analysis."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)
        scope = self.build_scope(store, 'order__store')
        channel_filter = _parse_channel_filter(request)

        product_revenue = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .values('product_id', 'product__name')
            .annotate(
                revenue=Sum(F('qty') * F('unit_price')),
                qty_sold=Sum('qty'),
            )
            .order_by('-revenue')
        )

        if not product_revenue:
            return Response({'products': [], 'total_revenue': 0})

        total_revenue = sum(p['revenue'] or 0 for p in product_revenue)
        items = []
        cumulative = 0
        for p in product_revenue:
            rev = p['revenue'] or 0
            cumulative += rev
            pct = round(cumulative / total_revenue * 100, 1) if total_revenue else 0
            share = round(rev / total_revenue * 100, 1) if total_revenue else 0
            if pct <= 80:
                rank = 'A'
            elif pct <= 95:
                rank = 'B'
            else:
                rank = 'C'
            items.append({
                'id': p['product_id'],
                'name': p['product__name'],
                'revenue': rev,
                'qty_sold': p['qty_sold'] or 0,
                'share_pct': share,
                'cumulative_pct': pct,
                'rank': rank,
            })

        return Response({'products': items, 'total_revenue': total_revenue})


class SalesForecastAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/forecast/?days=14 — sales forecast."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        forecast_days = _clamp_int(request.GET.get('days'), 14, hi=90)
        scope = self.build_scope(store, 'order__store')
        channel_filter = _parse_channel_filter(request)

        from .services.sales_forecast import generate_forecast
        result = generate_forecast(scope, forecast_days=forecast_days, channel_filter=channel_filter)
        return Response(result)


class SalesHeatmapAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/sales-heatmap/ — time-of-day x weekday sales heatmap."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)
        scope = self.build_scope(store, 'order__store')
        channel_filter = _parse_channel_filter(request)

        data = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .annotate(
                weekday=ExtractWeekDay('order__created_at'),
                hour=ExtractHour('order__created_at'),
            )
            .values('weekday', 'hour')
            .annotate(
                revenue=Sum(F('qty') * F('unit_price')),
                order_count=Count('order_id', distinct=True),
            )
            .order_by('weekday', 'hour')
        )

        matrix = defaultdict(lambda: defaultdict(lambda: {'revenue': 0, 'orders': 0}))
        for row in data:
            wd = row['weekday']
            hr = row['hour']
            matrix[wd][hr]['revenue'] = row['revenue'] or 0
            matrix[wd][hr]['orders'] = row['order_count'] or 0

        heatmap = []
        for wd in range(1, 8):
            for hr in range(24):
                cell = matrix[wd][hr]
                heatmap.append({
                    'weekday': wd,
                    'hour': hr,
                    'revenue': cell['revenue'],
                    'orders': cell['orders'],
                })

        return Response({'heatmap': heatmap})


class AOVTrendAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/aov-trend/?period=daily — Average Order Value trend."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        period = request.GET.get('period', 'daily')
        trunc_fn = PERIOD_TRUNC_MAP.get(period, PERIOD_TRUNC_MAP['daily'])
        scope = self.build_scope(store, 'order__store')
        since = _get_since_for_period(period)
        channel_filter = _parse_channel_filter(request)

        trend = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope, **channel_filter)
            .annotate(date=trunc_fn('order__created_at'))
            .values('date')
            .annotate(
                order_count=Count('order_id', distinct=True),
                total_revenue=Sum(F('qty') * F('unit_price')),
            )
            .order_by('date')
        )

        trend_list = []
        for t in trend:
            oc = t['order_count'] or 0
            rev = t['total_revenue'] or 0
            aov = round(rev / oc) if oc > 0 else 0
            trend_list.append({
                'date': t['date'].isoformat(),
                'order_count': oc,
                'total_revenue': rev,
                'aov': aov,
            })

        return Response({'trend': trend_list, 'period': period})


class SalesAnalysisTextAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/analysis-text/?type=menu_engineering&channel=ec"""

    VALID_TYPES = {
        'sales_trend', 'menu_engineering', 'abc_analysis',
        'forecast', 'heatmap', 'aov',
    }

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        analysis_type = request.GET.get('type', '')
        if analysis_type not in self.VALID_TYPES:
            return Response(
                {'detail': f'Invalid type. Valid: {", ".join(sorted(self.VALID_TYPES))}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope = self.build_scope(store, 'store')
        channel_filter = _parse_channel_filter(request)

        from .services.sales_analysis_text import SalesAnalysisEngine
        try:
            engine = SalesAnalysisEngine()
            result = engine.analyze(analysis_type, scope, channel_filter)
            return Response(result)
        except Exception:
            logger.exception("AI分析テキスト生成に失敗")
            return Response(
                {'detail': '分析テキストの生成に失敗しました'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChannelSalesAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/channel-sales/?period=daily — channel breakdown."""

    CHANNEL_LABELS = {
        'ec': 'ECショップ',
        'pos': 'POS',
        'table': 'テーブル注文',
        'reservation': '予約',
    }

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        period = request.GET.get('period', 'daily')
        trunc_fn = PERIOD_TRUNC_MAP.get(period, PERIOD_TRUNC_MAP['daily'])
        scope = self.build_scope(store, 'order__store')
        since = _get_since_for_period(period)

        settings = SiteSettings.load()
        channels = []
        if settings.show_admin_pos:
            channels.extend(['pos', 'table'])
        if settings.show_admin_ec_shop:
            channels.append('ec')
        if settings.show_admin_reservation:
            channels.append('reservation')

        if not channels:
            return Response({
                'channels': [],
                'trend': [],
                'channel_labels': self.CHANNEL_LABELS,
            })

        trend_qs = (
            OrderItem.objects
            .filter(
                order__created_at__gte=since,
                order__channel__in=channels,
                **scope,
            )
            .annotate(date=trunc_fn('order__created_at'))
            .values('date', 'order__channel')
            .annotate(total=Sum(F('qty') * F('unit_price')))
            .order_by('date', 'order__channel')
        )

        trend_list = [
            {
                'date': t['date'].isoformat(),
                'channel': t['order__channel'],
                'total': t['total'] or 0,
            }
            for t in trend_qs
        ]

        return Response({
            'channels': channels,
            'trend': trend_list,
            'channel_labels': self.CHANNEL_LABELS,
        })
