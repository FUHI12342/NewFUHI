# booking/views_dashboard_operations.py
"""Dashboard operations API views: Staff, Shift, LowStock, AutoOrder, KPI, NPS, Feedback, Checkin, ExternalData."""
import logging
from datetime import timedelta

from django.db.models import Count, Sum, Q, F, Avg
from django.db.models.functions import TruncDate, TruncWeek, ExtractHour
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Store, Schedule, OrderItem, Staff, Product, Order,
    ShiftPeriod, ShiftAssignment, CustomerFeedback, VisitorCount,
    TableSeat,
)
from .views_dashboard_base import DashboardAuthMixin, PERIOD_TRUNC_MAP, _clamp_int

logger = logging.getLogger(__name__)


class ReservationStatsAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/reservations/ — reservation statistics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        now = timezone.now()
        since = now - timedelta(days=90)
        scope = self.build_scope(store, 'staff__store')

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

        future_count = Schedule.objects.filter(
            start__gte=now, is_cancelled=False, is_temporary=False, **scope
        ).count()

        total = Schedule.objects.filter(start__gte=since, **scope).count()
        cancelled = Schedule.objects.filter(start__gte=since, is_cancelled=True, **scope).count()
        cancel_rate = round(cancelled / total, 4) if total > 0 else 0

        return Response({
            'daily': daily_list,
            'future_count': future_count,
            'cancel_rate': cancel_rate,
        })


class StaffPerformanceAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/staff-performance/ — staff metrics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        since = timezone.now() - timedelta(days=30)
        scope = self.build_scope(store, 'store')

        staff_type_param = request.GET.get('staff_type', '')
        staff_type_filter = {'staff_type': staff_type_param} if staff_type_param else {}

        staffs = (
            Staff.objects
            .filter(**scope, **staff_type_filter)
            .select_related('store')
            .annotate(
                reservation_count=Count(
                    'schedule',
                    filter=Q(
                        schedule__start__gte=since,
                        schedule__is_cancelled=False,
                        schedule__is_temporary=False,
                    ),
                ),
            )
        )

        staff_sales = (
            OrderItem.objects
            .filter(order__created_at__gte=since, order__schedule__staff__in=staffs)
            .values('order__schedule__staff_id')
            .annotate(total=Sum(F('qty') * F('unit_price')))
        )
        sales_map = {row['order__schedule__staff_id']: row['total'] or 0 for row in staff_sales}

        result = [
            {'name': s.name, 'reservations': s.reservation_count, 'sales': sales_map.get(s.id, 0)}
            for s in staffs
        ]

        return Response({'staff': result})


class ShiftSummaryAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/shift-summary/ — shift statistics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        now = timezone.now()
        current_month_start = now.replace(day=1).date()
        period_scope = self.build_scope(store, 'period__store')
        store_scope = self.build_scope(store, 'store')

        assignments = ShiftAssignment.objects.filter(date__gte=current_month_start, **period_scope)
        total_assignments = assignments.count()
        synced_assignments = assignments.filter(is_synced=True).count()

        open_periods = ShiftPeriod.objects.filter(status='open', **store_scope).count()

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


class LowStockAlertAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/low-stock/ — products below threshold."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        scope = self.build_scope(store, 'store')

        low_stock = (
            Product.objects
            .select_related('store')
            .filter(is_active=True, stock__lte=F('low_stock_threshold'), **scope)
            .order_by('stock')[:20]
        )

        products = [
            {'name': p.name, 'stock': p.stock, 'low_stock_threshold': p.low_stock_threshold}
            for p in low_stock
        ]

        return Response({'products': products})


class AutoOrderRecommendationAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/auto-order/ — auto-order recommendations."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        scope = self.build_scope(store, 'store')

        from .services.auto_order import compute_auto_order
        try:
            result = compute_auto_order(scope=scope)
            return Response(result)
        except Exception:
            logger.exception("自動発注推奨の生成に失敗")
            return Response({'detail': '内部エラーが発生しました'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class KPIScoreCardAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/kpi-scorecard/ — management KPIs."""

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
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 30, hi=365)
        now = timezone.now()
        since = now - timedelta(days=days)
        scope = self.build_scope(store, 'store')
        order_scope = self.build_scope(store, 'order__store')

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
        aov = round(total_revenue / total_orders) if total_orders > 0 else 0

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

        unique_days = (
            Order.objects
            .filter(created_at__gte=since, **scope)
            .annotate(date=TruncDate('created_at'))
            .values('date')
            .distinct()
            .count()
        )
        from .models import TableSeat
        stores = Store.objects.filter(**scope) if scope else Store.objects.all()
        table_count = TableSeat.objects.filter(store__in=stores).count() or 1
        table_turnover = round(total_orders / (unique_days * table_count), 2) if unique_days > 0 else 0

        product_scope = {k.replace('order__', ''): v for k, v in order_scope.items()} if order_scope else {}
        avg_margin = (
            Product.objects
            .filter(is_active=True, **product_scope)
            .aggregate(avg_margin=Avg('margin_rate'))
        )['avg_margin'] or 0
        food_cost_pct = round((1 - avg_margin) * 100, 1) if avg_margin > 0 else 0
        labor_cost_pct = 0
        prime_cost_pct = food_cost_pct + labor_cost_pct

        def _status(key, value, inverse=False):
            bench = self.BENCHMARKS[key]
            if bench['good'] is None:
                return 'neutral'
            if inverse:
                return 'good' if value <= bench['good'] else ('warn' if value <= bench['warn'] else 'bad')
            return 'good' if value >= bench['good'] else ('warn' if value >= bench['warn'] else 'bad')

        kpis = [
            {'key': 'aov', 'label': '客単価', 'value': aov, 'unit': '円', 'status': 'neutral', 'benchmark': None},
            {'key': 'total_revenue', 'label': '売上合計', 'value': total_revenue, 'unit': '円', 'status': 'neutral', 'benchmark': None},
            {'key': 'total_orders', 'label': '注文数', 'value': total_orders, 'unit': '件', 'status': 'neutral', 'benchmark': None},
            {'key': 'repeat_rate', 'label': 'リピート率', 'value': repeat_rate, 'unit': '%', 'status': _status('repeat_rate', repeat_rate), 'benchmark': self.BENCHMARKS['repeat_rate']},
            {'key': 'cancel_rate', 'label': 'キャンセル率', 'value': cancel_rate, 'unit': '%', 'status': _status('cancel_rate', cancel_rate, inverse=True), 'benchmark': self.BENCHMARKS['cancel_rate']},
            {'key': 'table_turnover', 'label': '回転率', 'value': table_turnover, 'unit': '回/日', 'status': _status('table_turnover', table_turnover), 'benchmark': self.BENCHMARKS['table_turnover']},
            {'key': 'food_cost_pct', 'label': '原価率', 'value': food_cost_pct, 'unit': '%', 'status': _status('food_cost_pct', food_cost_pct, inverse=True) if food_cost_pct > 0 else 'neutral', 'benchmark': self.BENCHMARKS['food_cost_pct']},
        ]

        return Response({
            'kpis': kpis,
            'period_days': days,
            'total_customers': total_customers,
        })


class CustomerFeedbackAPIView(DashboardAuthMixin, APIView):
    """POST: submit feedback (public), GET: list feedbacks (admin)."""
    permission_classes = []

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
            store_obj = Store.objects.get(pk=store_id)
        except Store.DoesNotExist:
            return Response({'detail': 'store not found'}, status=status.HTTP_404_NOT_FOUND)

        comment = data.get('comment', '')
        if nps >= 9:
            auto_sentiment = 'positive'
        elif nps >= 7:
            auto_sentiment = 'neutral'
        else:
            auto_sentiment = 'negative'

        fb = CustomerFeedback.objects.create(
            store=store_obj,
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
        store, err = self.get_user_store(request)
        if err:
            return err

        scope = self.build_scope(store, 'store')
        qs = CustomerFeedback.objects.select_related('store').filter(**scope).order_by('-created_at')[:100]
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


class NPSStatsAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/nps/ — NPS statistics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 90)
        now = timezone.now()
        since = now - timedelta(days=days)
        scope = self.build_scope(store, 'store')

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
            trend.append({'week': w['week'].strftime('%Y-%m-%d'), 'nps': w_nps, 'count': w['total']})

        sentiment_dist = {}
        for s in qs.values('sentiment').annotate(c=Count('id')):
            if s['sentiment']:
                sentiment_dist[s['sentiment']] = s['c']

        return Response({
            'nps_score': nps, 'total': total,
            'promoters': promoters, 'passives': passives, 'detractors': detractors,
            'avg_food': round(avgs['avg_food'] or 0, 1),
            'avg_service': round(avgs['avg_service'] or 0, 1),
            'avg_ambiance': round(avgs['avg_ambiance'] or 0, 1),
            'trend': trend, 'sentiment_dist': sentiment_dist,
        })


class ExternalDataAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/external-data/ — external data integration status."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        from .services.external_data import get_integration_status, get_weather_forecast, get_google_reviews

        service = request.GET.get('service')

        if service == 'weather':
            lat = request.GET.get('lat')
            lng = request.GET.get('lng')
            days = _clamp_int(request.GET.get('days'), 7, hi=14)
            try:
                lat = float(lat) if lat else None
                lng = float(lng) if lng else None
            except (ValueError, TypeError):
                lat, lng = None, None
            result = get_weather_forecast(lat=lat, lng=lng, days=days)
            return Response(result)

        if service == 'google_reviews':
            place_id = request.GET.get('place_id')
            result = get_google_reviews(place_id=place_id)
            return Response(result)

        integrations = get_integration_status()
        return Response({
            'integrations': integrations,
            'total': len(integrations),
            'configured_count': sum(1 for i in integrations if i['configured']),
        })


class CheckinStatsAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/checkin-stats/ — checkin statistics."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 30, lo=7, hi=90)
        now = timezone.now()
        since = now - timedelta(days=days)
        scope = self.build_scope(store, 'staff__store')

        base_qs = Schedule.objects.filter(
            start__gte=since, start__lte=now,
            is_temporary=False, is_cancelled=False,
            **scope,
        )

        daily = (
            base_qs
            .annotate(date=TruncDate('start'))
            .values('date')
            .annotate(
                total=Count('id'),
                checked_in=Count('id', filter=Q(is_checked_in=True)),
            )
            .order_by('date')
        )
        daily_list = []
        for d in daily:
            t = d['total']
            c = d['checked_in']
            rate = round(c / t, 4) if t > 0 else 0
            daily_list.append({
                'date': d['date'].isoformat(),
                'total': t, 'checked_in': c,
                'no_show': t - c, 'checkin_rate': rate,
            })

        total_all = base_qs.count()
        checked_all = base_qs.filter(is_checked_in=True).count()
        checkin_rate = round(checked_all / total_all, 4) if total_all > 0 else 0
        no_show_rate = round(1 - checkin_rate, 4) if total_all > 0 else 0

        by_staff = (
            base_qs
            .values('staff__name')
            .annotate(
                total=Count('id'),
                checked_in=Count('id', filter=Q(is_checked_in=True)),
            )
            .order_by('-total')
        )
        staff_list = []
        for s in by_staff:
            t = s['total']
            c = s['checked_in']
            staff_list.append({
                'staff_name': s['staff__name'],
                'total': t, 'checked_in': c,
                'checkin_rate': round(c / t, 4) if t > 0 else 0,
            })

        hourly = (
            base_qs
            .filter(is_checked_in=True)
            .annotate(hour=ExtractHour('checked_in_at'))
            .values('hour')
            .annotate(count=Count('id'))
            .order_by('hour')
        )
        hourly_list = [{'hour': h['hour'], 'count': h['count']} for h in hourly]

        return Response({
            'summary': {
                'total': total_all, 'checked_in': checked_all,
                'no_show': total_all - checked_all,
                'checkin_rate': checkin_rate, 'no_show_rate': no_show_rate,
                'days': days,
            },
            'daily': daily_list,
            'by_staff': staff_list,
            'hourly': hourly_list,
        })
