"""勤務実績ダッシュボード — 表示ビュー + JSON API"""
import logging
from datetime import date

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.translation import gettext as _

from booking.models import Store, Staff
from booking.services.attendance_summary import get_monthly_summary
from booking.views_restaurant_dashboard import AdminSidebarMixin

logger = logging.getLogger(__name__)


def _get_user_store(request):
    """Superuser: store_id param or None (all). Staff: own store."""
    if request.user.is_superuser:
        store_id = request.GET.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return None
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


class StaffPerformanceDashboardView(AdminSidebarMixin, TemplateView):
    """スタッフ勤務実績ダッシュボード"""
    template_name = 'admin/booking/staff_performance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        ctx.update({
            'title': _('勤務実績'),
            'has_permission': True,
            'stores': Store.objects.all(),
            'current_year': today.year,
            'current_month': today.month,
        })
        return ctx


class AttendancePerformanceAPIView(View):
    """GET /api/attendance/performance/"""

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'login required'}, status=403)

        today = date.today()
        try:
            year = int(request.GET.get('year', today.year))
            month = int(request.GET.get('month', today.month))
            if not (1 <= month <= 12):
                raise ValueError('month out of range')
            if not (2000 <= year <= 2100):
                raise ValueError('year out of range')
        except (TypeError, ValueError) as exc:
            return JsonResponse({'error': f'invalid parameter: {exc}'}, status=400)

        staff_id = None
        staff_id_raw = request.GET.get('staff_id')
        if staff_id_raw:
            try:
                staff_id = int(staff_id_raw)
            except (TypeError, ValueError):
                return JsonResponse({'error': 'invalid staff_id'}, status=400)

        store = _get_user_store(request)
        summary = get_monthly_summary(
            store=store, year=year, month=month, staff_id=staff_id,
        )
        return JsonResponse({'year': year, 'month': month, 'rows': summary})
