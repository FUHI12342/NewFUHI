"""シフトカレンダー管理 View（店長向けページ + ヘルパー）"""
import json
import logging
from datetime import date, timedelta, datetime

from django.http import HttpResponse
from django.views.generic import TemplateView
from django.template.loader import render_to_string
from django.utils.translation import gettext as _

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import (
    Store, Staff, ShiftPeriod, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory,
)

logger = logging.getLogger(__name__)


# ==============================
# ヘルパー関数
# ==============================

def _get_user_store(request):
    """リクエストユーザーの店舗を取得。見つからなければ None を返す。"""
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        # superuser にはデフォルト店舗を返す（明示的な選択がない場合）
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return None


def _get_week_dates(week_start_str=None):
    """週の開始日から7日分のリストを返す"""
    if week_start_str:
        try:
            start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        except ValueError:
            start = date.today()
    else:
        start = date.today()
    start = start - timedelta(days=start.weekday())
    return [start + timedelta(days=i) for i in range(7)]


def _render_week_grid(request, store, week_start_str=None):
    """週グリッドHTMLをレンダリングするヘルパー"""
    week_dates = _get_week_dates(week_start_str)
    staffs = Staff.objects.filter(store=store).order_by('name') if store else []

    assignments = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=week_dates[0],
        date__lte=week_dates[-1],
    ).select_related('staff') if store else []

    grid = {}
    for a in assignments:
        if a.staff_id not in grid:
            grid[a.staff_id] = {}
        grid[a.staff_id][a.date.isoformat()] = a

    templates = ShiftTemplate.objects.filter(store=store, is_active=True) if store else []

    return render_to_string('admin/booking/partials/shift_week_grid.html', {
        'staffs': staffs,
        'week_dates': week_dates,
        'grid': grid,
        'templates': templates,
        'week_start': week_dates[0].isoformat(),
        'prev_week': (week_dates[0] - timedelta(weeks=1)).isoformat(),
        'next_week': (week_dates[0] + timedelta(weeks=1)).isoformat(),
    }, request=request)


# ==============================
# 店長向けページ View
# ==============================

class ManagerShiftCalendarView(AdminSidebarMixin, TemplateView):
    """シフトカレンダー表示ページ"""
    template_name = 'admin/booking/shift_calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        week_dates = _get_week_dates(self.request.GET.get('week_start'))

        staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()
        staff_count = staffs.count()

        assign_qs = ShiftAssignment.objects.filter(
            period__store=store,
            date__gte=week_dates[0],
            date__lte=week_dates[-1],
        ).select_related('staff', 'period') if store else ShiftAssignment.objects.none()
        assignments = assign_qs

        templates = ShiftTemplate.objects.filter(store=store, is_active=True) if store else ShiftTemplate.objects.none()

        periods = ShiftPeriod.objects.filter(store=store).order_by('-year_month') if store else ShiftPeriod.objects.none()

        period_id = self.request.GET.get('period_id')
        if period_id:
            active_period = periods.filter(pk=period_id).first()
        else:
            active_period = periods.filter(status__in=['open', 'scheduled']).first()
        if not active_period:
            active_period = periods.first()

        request_stats = {}
        if active_period:
            from booking.models import ShiftRequest
            reqs = ShiftRequest.objects.filter(period=active_period)
            submitted_staff = reqs.values('staff').distinct().count()
            total_requests = reqs.count()
            request_stats = {
                'submitted_staff': submitted_staff,
                'total_requests': total_requests,
            }

        grid = {}
        for a in assignments:
            if a.staff_id not in grid:
                grid[a.staff_id] = {}
            grid[a.staff_id][a.date.isoformat()] = a

        publish_history = ShiftPublishHistory.objects.filter(
            period__store=store,
        ).select_related('published_by', 'period').order_by('-published_at')[:5] if store else []

        ctx.update({
            'title': _('シフトカレンダー'),
            'has_permission': True,
            'store': store,
            'stores': Store.objects.all(),
            'staffs': staffs,
            'staff_count': staff_count,
            'week_dates': week_dates,
            'grid': grid,
            'templates': templates,
            'periods': periods,
            'active_period': active_period,
            'request_stats': request_stats,
            'publish_history': publish_history,
            'week_start': week_dates[0].isoformat(),
            'prev_week': (week_dates[0] - timedelta(weeks=1)).isoformat(),
            'next_week': (week_dates[0] + timedelta(weeks=1)).isoformat(),
        })
        return ctx


class TodayShiftTimelineView(AdminSidebarMixin, TemplateView):
    """本日のシフト: 縦軸=時間、横軸=スタッフのタイムライン表示"""
    template_name = 'admin/booking/today_shift.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        today = date.today()

        staffs = list(
            Staff.objects.filter(store=store).order_by('name')
        ) if store else []

        assignments = ShiftAssignment.objects.filter(
            period__store=store,
            date=today,
        ).select_related('staff', 'period') if store else ShiftAssignment.objects.none()

        hours = list(range(9, 24))

        staff_shifts = {}
        for a in assignments:
            start_h = a.start_time.hour if a.start_time else a.start_hour
            end_h = a.end_time.hour if a.end_time else a.end_hour
            staff_shifts[a.staff_id] = {
                'start_hour': start_h,
                'end_hour': end_h,
                'color': a.color or '#3B82F6',
                'start_time': a.start_time,
                'end_time': a.end_time,
            }

        staff_shifts_json = json.dumps({
            str(k): {
                'start_hour': v['start_hour'],
                'end_hour': v['end_hour'],
                'color': v['color'],
            }
            for k, v in staff_shifts.items()
        })

        ctx.update({
            'title': _('本日のシフト'),
            'has_permission': True,
            'store': store,
            'today': today,
            'staffs': staffs,
            'hours': hours,
            'staff_shifts': staff_shifts,
            'staff_shifts_json': staff_shifts_json,
        })
        return ctx
