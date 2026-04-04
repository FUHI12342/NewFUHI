# booking/views_dashboard_analytics.py
"""Dashboard analytics API views: Cohort, RFM, Basket, CLV, Visitor, Insights."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum, Q, F
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Order, BusinessInsight
from .views_dashboard_base import DashboardAuthMixin, _clamp_int

logger = logging.getLogger(__name__)


class CohortAnalysisAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/cohort/ — monthly cohort retention analysis."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        months = _clamp_int(request.GET.get('months'), 6, hi=24)
        now = timezone.now()
        since = now - timedelta(days=months * 31)
        scope = self.build_scope(store, 'store')

        orders = (
            Order.objects
            .filter(created_at__gte=since, customer_line_user_hash__isnull=False,
                    **scope, **self.build_demo_filter())
            .exclude(customer_line_user_hash='')
            .annotate(month=TruncMonth('created_at'))
            .values('customer_line_user_hash', 'month')
            .distinct()
        )

        customer_months = defaultdict(set)
        for o in orders:
            cid = o['customer_line_user_hash']
            customer_months[cid].add(o['month'].date().replace(day=1))

        customer_cohort = {}
        for cid, months_set in customer_months.items():
            first_month = min(months_set)
            customer_cohort[cid] = {'cohort': first_month, 'months': months_set}

        cohort_counts = defaultdict(lambda: defaultdict(int))
        cohort_sizes = defaultdict(int)

        for cid, info in customer_cohort.items():
            cohort = info['cohort']
            cohort_sizes[cohort] += 1
            for active_month in info['months']:
                offset = (active_month.year - cohort.year) * 12 + (active_month.month - cohort.month)
                cohort_counts[cohort][offset] += 1

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


class RFMAnalysisAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/rfm/ — RFM segmentation analysis."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 365, hi=730)
        scope = self.build_scope(store, 'order__store')

        from .services.rfm_analysis import compute_rfm
        customers = compute_rfm(scope=scope, days=days)

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


class BasketAnalysisAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/basket/ — market basket analysis."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        days = _clamp_int(request.GET.get('days'), 90, hi=365)
        scope = self.build_scope(store, 'order__store')

        from .services.basket_analysis import analyze_basket
        result = analyze_basket(scope=scope, days=days)
        return Response(result)


class CLVAnalysisAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/clv/?months=6 — CLV customer lifetime value."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        months = _clamp_int(request.GET.get('months'), 6, hi=24)
        scope = self.build_scope(store, 'order__store')

        from .services.clv_analysis import compute_clv
        try:
            result = compute_clv(scope=scope, months=months)
            return Response(result)
        except Exception:
            logger.exception("CLV分析の生成に失敗")
            return Response({'detail': '内部エラーが発生しました'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VisitorForecastAPIView(DashboardAuthMixin, APIView):
    """GET /api/dashboard/visitor-forecast/?days=14 — visitor prediction."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        forecast_days = _clamp_int(request.GET.get('days'), 14, hi=90)
        scope = self.build_scope(store, 'store')

        from .services.visitor_forecast import compute_visitor_forecast
        try:
            result = compute_visitor_forecast(scope=scope, forecast_days=forecast_days)
            return Response(result)
        except Exception:
            logger.exception("来客予測の生成に失敗")
            return Response({'detail': '内部エラーが発生しました'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InsightsAPIView(DashboardAuthMixin, APIView):
    """GET/POST /api/dashboard/insights/ — business insights."""

    def get(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        scope = self.build_scope(store, 'store')
        unread_only = request.GET.get('unread', '').lower() in ('1', 'true')
        qs = BusinessInsight.objects.select_related('store').filter(
            **scope, **self.build_demo_filter())
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.order_by('-created_at')[:50]

        insights = [{
            'id': ins.id,
            'category': ins.category,
            'severity': ins.severity,
            'title': ins.title,
            'message': ins.message,
            'data': ins.data,
            'is_read': ins.is_read,
            'created_at': ins.created_at.isoformat(),
        } for ins in qs]

        return Response({'insights': insights})

    def post(self, request):
        store, err = self.get_user_store(request)
        if err:
            return err

        action = request.data.get('action', 'generate')

        if action == 'mark_read':
            insight_id = request.data.get('insight_id')
            if insight_id:
                BusinessInsight.objects.filter(id=insight_id).update(is_read=True)
                return Response({'status': 'ok'})
            scope = self.build_scope(store, 'store')
            BusinessInsight.objects.filter(is_read=False, **scope).update(is_read=True)
            return Response({'status': 'ok'})

        # action == 'generate'
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
        except Exception:
            logger.exception("Insight generation failed")
            return Response({'detail': '内部エラーが発生しました'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
