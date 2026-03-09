"""来客分析View + API"""
import json
import logging
from datetime import date, timedelta

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import Store, Staff, VisitorCount

logger = logging.getLogger(__name__)


def _get_user_store(request):
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


class VisitorAnalyticsDashboardView(AdminSidebarMixin, TemplateView):
    """来客分析ダッシュボード"""
    template_name = 'admin/booking/visitor_analytics.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        today = date.today()

        # 今日のサマリー
        today_data = VisitorCount.objects.filter(
            store=store, date=today,
        ) if store else VisitorCount.objects.none()

        from django.db.models import Sum
        today_summary = today_data.aggregate(
            total_visitors=Sum('estimated_visitors'),
            total_orders=Sum('order_count'),
        )

        ctx.update({
            'title': '来客分析',
            'has_permission': True,
            'store': store,
            'stores': Store.objects.all(),
            'today_visitors': today_summary['total_visitors'] or 0,
            'today_orders': today_summary['total_orders'] or 0,
        })
        return ctx


class VisitorCountAPIView(View):
    """時系列来客データ"""

    def get(self, request):
        store = _get_user_store(request)
        range_param = request.GET.get('range', '7')

        try:
            days = int(range_param)
        except ValueError:
            days = 7

        date_from = date.today() - timedelta(days=days)
        records = VisitorCount.objects.filter(
            store=store,
            date__gte=date_from,
        ).order_by('date', 'hour') if store else []

        data = [{
            'date': r.date.isoformat(),
            'hour': r.hour,
            'pir_count': r.pir_count,
            'estimated_visitors': r.estimated_visitors,
            'order_count': r.order_count,
        } for r in records]

        return JsonResponse(data, safe=False)


class VisitorHeatmapAPIView(View):
    """曜日×時間ヒートマップデータ"""

    def get(self, request):
        store = _get_user_store(request)
        weeks = int(request.GET.get('weeks', '4'))

        from booking.services.visitor_analytics import get_heatmap_data
        data = get_heatmap_data(store, weeks=weeks) if store else {}
        return JsonResponse(data)


class ConversionAnalyticsAPIView(View):
    """来客数→注文数コンバージョン率"""

    def get(self, request):
        store = _get_user_store(request)
        days = int(request.GET.get('days', '30'))
        date_from = date.today() - timedelta(days=days)

        from booking.services.visitor_analytics import calculate_conversion_rate
        data = calculate_conversion_rate(store, date_from, date.today()) if store else {}
        return JsonResponse(data)
