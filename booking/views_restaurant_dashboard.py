# booking/views_restaurant_dashboard.py
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum, Q, F, Avg
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, ExtractHour, ExtractWeekDay
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Store, Schedule, Order, OrderItem, Staff, Product, DashboardLayout, DEFAULT_DASHBOARD_LAYOUT,
    ShiftPeriod, ShiftAssignment, BusinessInsight, CustomerFeedback,
)

logger = logging.getLogger(__name__)


def _clamp_int(value, default, lo=1, hi=365):
    """Parse and clamp an integer query parameter."""
    try:
        return max(lo, min(int(value), hi))
    except (TypeError, ValueError):
        return default


class AdminSidebarMixin:
    """Jazzminサイドバー表示に必要なコンテキストを注入"""
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from booking.admin_site import custom_site
        ctx['available_apps'] = custom_site.get_app_list(self.request)
        ctx['has_permission'] = True
        return ctx


def _get_store_scope(request):
    """Return store filter kwargs based on user role."""
    if request.user.is_superuser:
        return {}
    try:
        staff = request.user.staff
        return {'store': staff.store}
    except (Staff.DoesNotExist, AttributeError):
        return {'pk': -1}  # No results


class RestaurantDashboardView(AdminSidebarMixin, TemplateView):
    """Restaurant activity dashboard (admin)."""
    template_name = 'admin/booking/restaurant_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = '売上分析'
        ctx['has_permission'] = True
        return ctx


class DashboardLayoutAPIView(APIView):
    """GET/PUT /api/dashboard/layout/ — ダッシュボードレイアウト保存/読込."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        try:
            layout = DashboardLayout.objects.get(user=request.user)
            return Response({
                'layout': layout.layout_json,
            })
        except DashboardLayout.DoesNotExist:
            return Response({
                'layout': DEFAULT_DASHBOARD_LAYOUT,
            })

    def put(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        layout_data = request.data.get('layout')

        obj, created = DashboardLayout.objects.get_or_create(
            user=request.user,
            defaults={
                'layout_json': layout_data if layout_data is not None else DEFAULT_DASHBOARD_LAYOUT,
            }
        )
        if not created:
            if layout_data is not None:
                obj.layout_json = layout_data
            obj.save()

        return Response({'ok': True})


class ReservationStatsAPIView(APIView):
    """GET /api/dashboard/reservations/ — reservation statistics."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        since = now - timedelta(days=90)

        scope = {}
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
                scope = {'staff__store': staff.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Daily counts (last 90 days)
        daily = (
            Schedule.objects
            .filter(start__gte=since, **scope)
            .annotate(date=TruncDate('start'))
            .values('date')
            .annotate(
                count=Count('id'),
                cancelled=Count('id', filter=Q(is_cancelled=True)),
            )
            .order_by('date')
        )

        daily_list = [{'date': d['date'].isoformat(), 'count': d['count'], 'cancelled': d['cancelled']} for d in daily]

        # Future reservations
        future_count = Schedule.objects.filter(
            start__gte=now, is_cancelled=False, is_temporary=False, **scope
        ).count()

        # Overall cancel rate
        total = Schedule.objects.filter(start__gte=since, **scope).count()
        cancelled = Schedule.objects.filter(start__gte=since, is_cancelled=True, **scope).count()
        cancel_rate = round(cancelled / total, 4) if total > 0 else 0

        return Response({
            'daily': daily_list,
            'future_count': future_count,
            'cancel_rate': cancel_rate,
        })


class SalesStatsAPIView(APIView):
    """GET /api/dashboard/sales/?period=daily — sales statistics."""

    TRUNC_MAP = {
        'daily': TruncDate,
        'weekly': TruncWeek,
        'monthly': TruncMonth,
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        period = request.GET.get('period', 'daily')
        trunc_fn = self.TRUNC_MAP.get(period, TruncDate)

        scope = {}
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
                scope = {'order__store': staff.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        since = timezone.now() - timedelta(days=90)

        # Sales trend
        trend = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
            .annotate(date=trunc_fn('order__created_at'))
            .values('date')
            .annotate(total=Sum(F('qty') * F('unit_price')))
            .order_by('date')
        )
        trend_list = [{'date': t['date'].isoformat(), 'total': t['total'] or 0} for t in trend]

        # Top 10 products
        top_products = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
            .values('product__name')
            .annotate(total=Sum('qty'))
            .order_by('-total')[:10]
        )
        products_list = [{'name': p['product__name'], 'total': p['total']} for p in top_products]

        return Response({'trend': trend_list, 'top_products': products_list})


class StaffPerformanceAPIView(APIView):
    """GET /api/dashboard/staff-performance/ — staff metrics."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        since = timezone.now() - timedelta(days=30)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        staffs = Staff.objects.filter(**scope)
        result = []
        for s in staffs:
            reservations = Schedule.objects.filter(
                staff=s, start__gte=since, is_cancelled=False, is_temporary=False,
            ).count()
            sales = (
                OrderItem.objects
                .filter(order__schedule__staff=s, order__created_at__gte=since)
                .aggregate(total=Sum(F('qty') * F('unit_price')))
            )['total'] or 0
            result.append({'name': s.name, 'reservations': reservations, 'sales': sales})

        return Response({'staff': result})


class ShiftSummaryAPIView(APIView):
    """GET /api/dashboard/shift-summary/ — shift statistics for dashboard."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        current_month_start = now.replace(day=1).date()

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'period__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Total assignments for current month
        assignments = ShiftAssignment.objects.filter(
            date__gte=current_month_start,
            **scope,
        )
        total_assignments = assignments.count()
        synced_assignments = assignments.filter(is_synced=True).count()

        # Open periods
        store_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                store_scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                store_scope = {'pk': -1}

        open_periods = ShiftPeriod.objects.filter(
            status='open', **store_scope,
        ).count()

        # Per-staff breakdown
        staff_shifts = (
            assignments
            .values('staff__name')
            .annotate(
                total=Count('id'),
                synced=Count('id', filter=Q(is_synced=True)),
            )
            .order_by('-total')
        )
        staff_list = [
            {'name': s['staff__name'], 'total': s['total'], 'synced': s['synced']}
            for s in staff_shifts
        ]

        return Response({
            'total_assignments': total_assignments,
            'synced_assignments': synced_assignments,
            'open_periods': open_periods,
            'staff_shifts': staff_list,
        })


class LowStockAlertAPIView(APIView):
    """GET /api/dashboard/low-stock/ — products below low_stock_threshold."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        low_stock = Product.objects.filter(
            is_active=True,
            stock__lte=F('low_stock_threshold'),
            **scope,
        ).order_by('stock')[:20]

        products = [
            {
                'name': p.name,
                'stock': p.stock,
                'low_stock_threshold': p.low_stock_threshold,
            }
            for p in low_stock
        ]

        return Response({'products': products})


class MenuEngineeringAPIView(APIView):
    """GET /api/dashboard/menu-engineering/ — menu engineering matrix.

    Classifies products into 4 quadrants:
      - Stars:       high popularity, high profitability
      - Plowhorses:  high popularity, low profitability
      - Puzzles:     low popularity, high profitability
      - Dogs:        low popularity, low profitability
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)

        scope = {}
        product_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
                product_scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Aggregate: total qty sold per product (popularity) and revenue
        product_stats = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
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

        # Classify into quadrants
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


class ABCAnalysisAPIView(APIView):
    """GET /api/dashboard/abc-analysis/ — ABC (Pareto) analysis.

    Classifies products by revenue contribution:
      - A: top 20% of cumulative revenue (most valuable)
      - B: next 30% (moderate)
      - C: remaining 50% (least valuable)
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Revenue per product
        product_revenue = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
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

        return Response({
            'products': items,
            'total_revenue': total_revenue,
        })


class SalesForecastAPIView(APIView):
    """GET /api/dashboard/forecast/?days=14 — sales forecast."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        forecast_days = _clamp_int(request.GET.get('days'), 14, hi=90)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        from .services.sales_forecast import generate_forecast
        result = generate_forecast(scope, forecast_days=forecast_days)
        return Response(result)


class SalesHeatmapAPIView(APIView):
    """GET /api/dashboard/sales-heatmap/ — time-of-day × weekday sales heatmap."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        since = timezone.now() - timedelta(days=days)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Aggregate by weekday × hour
        data = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
            .annotate(
                weekday=ExtractWeekDay('order__created_at'),   # 1=Sun … 7=Sat
                hour=ExtractHour('order__created_at'),
            )
            .values('weekday', 'hour')
            .annotate(
                revenue=Sum(F('qty') * F('unit_price')),
                order_count=Count('order_id', distinct=True),
            )
            .order_by('weekday', 'hour')
        )

        # Build 7×24 matrix
        matrix = defaultdict(lambda: defaultdict(lambda: {'revenue': 0, 'orders': 0}))
        for row in data:
            wd = row['weekday']   # 1-7
            hr = row['hour']     # 0-23
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


class AOVTrendAPIView(APIView):
    """GET /api/dashboard/aov-trend/?period=daily — Average Order Value trend."""

    TRUNC_MAP = {
        'daily': TruncDate,
        'weekly': TruncWeek,
        'monthly': TruncMonth,
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        period = request.GET.get('period', 'daily')
        trunc_fn = self.TRUNC_MAP.get(period, TruncDate)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        since = timezone.now() - timedelta(days=90)

        trend = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **scope)
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


class CohortAnalysisAPIView(APIView):
    """GET /api/dashboard/cohort/ — monthly cohort retention analysis."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        months = _clamp_int(request.GET.get('months'), 6, hi=24)
        now = timezone.now()
        since = now - timedelta(days=months * 31)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Get orders with customer identification
        orders = (
            Order.objects
            .filter(created_at__gte=since, customer_line_user_hash__isnull=False, **scope)
            .exclude(customer_line_user_hash='')
            .annotate(month=TruncMonth('created_at'))
            .values('customer_line_user_hash', 'month')
            .distinct()
        )

        # Group by customer: find first month (cohort) and all active months
        customer_months = defaultdict(set)
        for o in orders:
            cid = o['customer_line_user_hash']
            customer_months[cid].add(o['month'].date().replace(day=1))

        # Build cohort data
        customer_cohort = {}
        for cid, months_set in customer_months.items():
            first_month = min(months_set)
            customer_cohort[cid] = {'cohort': first_month, 'months': months_set}

        # Aggregate: for each cohort month, count users active in subsequent months
        cohort_counts = defaultdict(lambda: defaultdict(int))
        cohort_sizes = defaultdict(int)

        for cid, info in customer_cohort.items():
            cohort = info['cohort']
            cohort_sizes[cohort] += 1
            for active_month in info['months']:
                offset = (active_month.year - cohort.year) * 12 + (active_month.month - cohort.month)
                cohort_counts[cohort][offset] += 1

        # Build response
        cohorts = []
        for cohort_month in sorted(cohort_sizes.keys()):
            size = cohort_sizes[cohort_month]
            retention = {}
            for offset, count in sorted(cohort_counts[cohort_month].items()):
                retention[str(offset)] = {
                    'count': count,
                    'rate': round(count / size, 4) if size > 0 else 0,
                }
            cohorts.append({
                'cohort': cohort_month.isoformat(),
                'size': size,
                'retention': retention,
            })

        return Response({'cohorts': cohorts})


class RFMAnalysisAPIView(APIView):
    """GET /api/dashboard/rfm/ — RFM segmentation analysis."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 365, hi=730)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        from .services.rfm_analysis import compute_rfm
        customers = compute_rfm(scope=scope, days=days)

        # Segment summary
        segment_counts = defaultdict(int)
        for c in customers:
            segment_counts[c['segment']] += 1

        segments = [
            {'segment': seg, 'count': cnt}
            for seg, cnt in sorted(segment_counts.items(), key=lambda x: -x[1])
        ]

        return Response({
            'customers': customers,
            'segments': segments,
            'total_customers': len(customers),
        })


class BasketAnalysisAPIView(APIView):
    """GET /api/dashboard/basket/ — market basket analysis (association rules)."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 90, hi=365)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        from .services.basket_analysis import analyze_basket
        result = analyze_basket(scope=scope, days=days)
        return Response(result)


class InsightsAPIView(APIView):
    """GET  /api/dashboard/insights/ — list insights.
       POST /api/dashboard/insights/ — generate new insights or mark read.
    """

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        unread_only = request.GET.get('unread', '').lower() in ('1', 'true')
        qs = BusinessInsight.objects.filter(**scope)
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.order_by('-created_at')[:50]

        insights = []
        for ins in qs:
            insights.append({
                'id': ins.id,
                'category': ins.category,
                'severity': ins.severity,
                'title': ins.title,
                'message': ins.message,
                'data': ins.data,
                'is_read': ins.is_read,
                'created_at': ins.created_at.isoformat(),
            })

        return Response({'insights': insights})

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action', 'generate')

        if action == 'mark_read':
            insight_id = request.data.get('insight_id')
            if insight_id:
                BusinessInsight.objects.filter(id=insight_id).update(is_read=True)
                return Response({'status': 'ok'})
            # Mark all read
            scope = {}
            if not request.user.is_superuser:
                try:
                    s = request.user.staff
                    scope = {'store': s.store}
                except (Staff.DoesNotExist, AttributeError):
                    pass
            BusinessInsight.objects.filter(is_read=False, **scope).update(is_read=True)
            return Response({'status': 'ok'})

        # action == 'generate'
        store = None
        if not request.user.is_superuser:
            try:
                store = request.user.staff.store
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        from .services.insight_engine import generate_insights
        try:
            created = generate_insights(store=store)
            return Response({
                'status': 'ok',
                'created_count': len(created),
                'insights': [
                    {
                        'id': ins.id,
                        'category': ins.category,
                        'severity': ins.severity,
                        'title': ins.title,
                        'message': ins.message,
                    }
                    for ins in created
                ],
            })
        except Exception as e:
            logger.exception("Insight generation failed")
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KPIScoreCardAPIView(APIView):
    """GET /api/dashboard/kpi-scorecard/ — management KPIs with benchmarks."""

    # Industry benchmarks for restaurant business
    BENCHMARKS = {
        'food_cost_pct': {'good': 30, 'warn': 35, 'label': '原価率 (%)'},
        'labor_cost_pct': {'good': 25, 'warn': 30, 'label': '人件費率 (%)'},
        'prime_cost_pct': {'good': 60, 'warn': 65, 'label': 'プライムコスト (%)'},
        'aov': {'good': None, 'warn': None, 'label': '客単価 (円)'},
        'table_turnover': {'good': 3.0, 'warn': 2.0, 'label': '回転率'},
        'repeat_rate': {'good': 40, 'warn': 25, 'label': 'リピート率 (%)'},
        'cancel_rate': {'good': 10, 'warn': 20, 'label': 'キャンセル率 (%)'},
    }

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = _clamp_int(request.GET.get('days'), 30, hi=365)
        now = timezone.now()
        since = now - timedelta(days=days)

        scope = {}
        order_scope = {}
        if not request.user.is_superuser:
            try:
                s = request.user.staff
                scope = {'store': s.store}
                order_scope = {'order__store': s.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        # Revenue
        revenue_data = (
            OrderItem.objects
            .filter(order__created_at__gte=since, **order_scope)
            .aggregate(
                total_revenue=Sum(F('qty') * F('unit_price')),
                total_orders=Count('order_id', distinct=True),
            )
        )
        total_revenue = revenue_data['total_revenue'] or 0
        total_orders = revenue_data['total_orders'] or 0

        # AOV
        aov = round(total_revenue / total_orders) if total_orders > 0 else 0

        # Repeat rate
        customer_orders = (
            Order.objects
            .filter(created_at__gte=since, customer_line_user_hash__isnull=False, **scope)
            .exclude(customer_line_user_hash='')
            .values('customer_line_user_hash')
            .annotate(visit_count=Count('id'))
        )
        total_customers = customer_orders.count()
        repeat_customers = customer_orders.filter(visit_count__gte=2).count()
        repeat_rate = round(repeat_customers / total_customers * 100, 1) if total_customers > 0 else 0

        # Cancel rate
        total_reservations = Schedule.objects.filter(
            staff__store__in=Store.objects.filter(**scope) if scope else Store.objects.all(),
            start__gte=since,
        ).count()
        cancelled = Schedule.objects.filter(
            staff__store__in=Store.objects.filter(**scope) if scope else Store.objects.all(),
            start__gte=since,
            is_cancelled=True,
        ).count()
        cancel_rate = round(cancelled / total_reservations * 100, 1) if total_reservations > 0 else 0

        # Table turnover (orders / unique dates / estimated tables)
        unique_days = (
            Order.objects
            .filter(created_at__gte=since, **scope)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .distinct()
            .count()
        )
        # Estimate seats from TableSeat if available
        from .models import TableSeat
        stores = Store.objects.filter(**scope) if scope else Store.objects.all()
        table_count = TableSeat.objects.filter(store__in=stores).count() or 1
        table_turnover = round(total_orders / (unique_days * table_count), 2) if unique_days > 0 else 0

        # Food cost (estimate from product margin_rate if available)
        avg_margin = (
            Product.objects
            .filter(is_active=True, **{k.replace('order__', ''): v for k, v in order_scope.items()} if order_scope else {})
            .aggregate(avg_margin=Avg('margin_rate'))
        )['avg_margin'] or 0
        food_cost_pct = round((1 - avg_margin) * 100, 1) if avg_margin > 0 else 0

        # Labor cost (placeholder — would need payroll data)
        labor_cost_pct = 0
        prime_cost_pct = food_cost_pct + labor_cost_pct

        def _status(key, value, inverse=False):
            bench = self.BENCHMARKS[key]
            if bench['good'] is None:
                return 'neutral'
            if inverse:
                if value <= bench['good']:
                    return 'good'
                elif value <= bench['warn']:
                    return 'warn'
                return 'bad'
            else:
                if value >= bench['good']:
                    return 'good'
                elif value >= bench['warn']:
                    return 'warn'
                return 'bad'

        kpis = [
            {
                'key': 'aov', 'label': '客単価', 'value': aov,
                'unit': '円', 'status': 'neutral',
                'benchmark': None,
            },
            {
                'key': 'total_revenue', 'label': '売上合計', 'value': total_revenue,
                'unit': '円', 'status': 'neutral',
                'benchmark': None,
            },
            {
                'key': 'total_orders', 'label': '注文数', 'value': total_orders,
                'unit': '件', 'status': 'neutral',
                'benchmark': None,
            },
            {
                'key': 'repeat_rate', 'label': 'リピート率', 'value': repeat_rate,
                'unit': '%', 'status': _status('repeat_rate', repeat_rate),
                'benchmark': self.BENCHMARKS['repeat_rate'],
            },
            {
                'key': 'cancel_rate', 'label': 'キャンセル率', 'value': cancel_rate,
                'unit': '%', 'status': _status('cancel_rate', cancel_rate, inverse=True),
                'benchmark': self.BENCHMARKS['cancel_rate'],
            },
            {
                'key': 'table_turnover', 'label': '回転率', 'value': table_turnover,
                'unit': '回/日', 'status': _status('table_turnover', table_turnover),
                'benchmark': self.BENCHMARKS['table_turnover'],
            },
            {
                'key': 'food_cost_pct', 'label': '原価率', 'value': food_cost_pct,
                'unit': '%', 'status': _status('food_cost_pct', food_cost_pct, inverse=True) if food_cost_pct > 0 else 'neutral',
                'benchmark': self.BENCHMARKS['food_cost_pct'],
            },
        ]

        return Response({
            'kpis': kpis,
            'period_days': days,
            'total_customers': total_customers,
        })


class CustomerFeedbackAPIView(APIView):
    """POST: submit feedback (public), GET: list feedbacks (admin)."""

    def post(self, request):
        """Submit customer feedback — no auth required (QR survey)."""
        data = request.data
        nps = data.get('nps_score')
        store_id = data.get('store_id')
        if nps is None or store_id is None:
            return Response({'detail': 'nps_score and store_id required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            nps = int(nps)
            if not 0 <= nps <= 10:
                raise ValueError
        except (ValueError, TypeError):
            return Response({'detail': 'nps_score must be 0-10'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            store = Store.objects.get(pk=store_id)
        except Store.DoesNotExist:
            return Response({'detail': 'store not found'}, status=status.HTTP_404_NOT_FOUND)

        # Simple sentiment from NPS if no comment analysis
        comment = data.get('comment', '')
        if nps >= 9:
            auto_sentiment = 'positive'
        elif nps >= 7:
            auto_sentiment = 'neutral'
        else:
            auto_sentiment = 'negative'

        fb = CustomerFeedback.objects.create(
            store=store,
            order_id=data.get('order_id'),
            customer_hash=data.get('customer_hash', ''),
            nps_score=nps,
            food_rating=min(max(int(data.get('food_rating', 3)), 1), 5),
            service_rating=min(max(int(data.get('service_rating', 3)), 1), 5),
            ambiance_rating=min(max(int(data.get('ambiance_rating', 3)), 1), 5),
            comment=comment,
            sentiment=auto_sentiment,
        )
        return Response({'status': 'ok', 'id': fb.id}, status=status.HTTP_201_CREATED)

    def get(self, request):
        """List feedbacks — admin only."""
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        scope = {}
        if not request.user.is_superuser:
            try:
                scope = {'store': request.user.staff.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        qs = CustomerFeedback.objects.filter(**scope).order_by('-created_at')[:100]
        feedbacks = [{
            'id': f.id,
            'nps_score': f.nps_score,
            'nps_category': f.nps_category,
            'food_rating': f.food_rating,
            'service_rating': f.service_rating,
            'ambiance_rating': f.ambiance_rating,
            'comment': f.comment,
            'sentiment': f.sentiment,
            'created_at': f.created_at.isoformat(),
        } for f in qs]
        return Response({'feedbacks': feedbacks})


class NPSStatsAPIView(APIView):
    """GET /api/dashboard/nps/ — NPS statistics and trends."""

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        days = int(request.GET.get('days', 90))
        now = timezone.now()
        since = now - timedelta(days=days)

        scope = {}
        if not request.user.is_superuser:
            try:
                scope = {'store': request.user.staff.store}
            except (Staff.DoesNotExist, AttributeError):
                return Response({'detail': 'no store access'}, status=status.HTTP_403_FORBIDDEN)

        qs = CustomerFeedback.objects.filter(created_at__gte=since, **scope)
        total = qs.count()

        if total == 0:
            return Response({
                'nps_score': 0, 'total': 0,
                'promoters': 0, 'passives': 0, 'detractors': 0,
                'avg_food': 0, 'avg_service': 0, 'avg_ambiance': 0,
                'trend': [], 'sentiment_dist': {},
            })

        promoters = qs.filter(nps_score__gte=9).count()
        detractors = qs.filter(nps_score__lte=6).count()
        passives = total - promoters - detractors
        nps = round((promoters - detractors) / total * 100, 1)

        avgs = qs.aggregate(
            avg_food=Avg('food_rating'),
            avg_service=Avg('service_rating'),
            avg_ambiance=Avg('ambiance_rating'),
        )

        # Weekly NPS trend
        weekly = (
            qs.annotate(week=TruncWeek('created_at'))
            .values('week')
            .annotate(
                total=Count('id'),
                promo=Count('id', filter=Q(nps_score__gte=9)),
                detract=Count('id', filter=Q(nps_score__lte=6)),
            )
            .order_by('week')
        )
        trend = []
        for w in weekly:
            w_nps = round((w['promo'] - w['detract']) / w['total'] * 100, 1) if w['total'] > 0 else 0
            trend.append({
                'week': w['week'].strftime('%Y-%m-%d'),
                'nps': w_nps,
                'count': w['total'],
            })

        # Sentiment distribution
        sentiment_dist = {}
        for s in qs.values('sentiment').annotate(c=Count('id')):
            if s['sentiment']:
                sentiment_dist[s['sentiment']] = s['c']

        return Response({
            'nps_score': nps,
            'total': total,
            'promoters': promoters,
            'passives': passives,
            'detractors': detractors,
            'avg_food': round(avgs['avg_food'] or 0, 1),
            'avg_service': round(avgs['avg_service'] or 0, 1),
            'avg_ambiance': round(avgs['avg_ambiance'] or 0, 1),
            'trend': trend,
            'sentiment_dist': sentiment_dist,
        })
