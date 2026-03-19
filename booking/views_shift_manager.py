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
    ShiftTemplate, ShiftPublishHistory, ShiftRequest,
    ShiftVacancy, ShiftSwapRequest,
)
from booking.services.shift_scheduler import get_required_counts

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


def _render_week_grid(request, store, week_start_str=None, staff_type_filter=None):
    """週グリッドHTMLをレンダリングするヘルパー（後方互換）"""
    return _render_calendar_section(request, store, week_start_str, staff_type_filter)


def _render_calendar_section(request, store, week_start_str=None, staff_type_filter=None):
    """ツールバー + 週グリッドHTMLをレンダリング（HTMX partial 対応）"""
    week_dates = _get_week_dates(week_start_str)

    all_staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()
    cast_staffs = list(all_staffs.filter(staff_type='fortune_teller'))
    store_staffs = list(all_staffs.filter(staff_type='store_staff'))

    if staff_type_filter == 'fortune_teller':
        staffs = cast_staffs
    elif staff_type_filter == 'store_staff':
        staffs = store_staffs
    else:
        staffs = list(all_staffs)

    assign_qs = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=week_dates[0],
        date__lte=week_dates[-1],
    ).select_related('staff') if store else ShiftAssignment.objects.none()

    grid = {}
    for a in assign_qs:
        if a.staff_id not in grid:
            grid[a.staff_id] = {}
        grid[a.staff_id][a.date.isoformat()] = a

    templates = ShiftTemplate.objects.filter(store=store, is_active=True) if store else []

    # active_period を取得
    period_id = request.GET.get('period_id')
    active_period = None
    if period_id:
        active_period = ShiftPeriod.objects.filter(pk=period_id, store=store).first()
    if not active_period:
        active_period = ShiftPeriod.objects.filter(
            store=store, status__in=['open', 'scheduled'],
        ).order_by('-year_month').first()
    if not active_period:
        active_period = ShiftPeriod.objects.filter(store=store).order_by('-year_month').first()

    # 必要人数 vs 配置人数カバレッジ
    coverage = {}
    if store:
        for d in week_dates:
            required = get_required_counts(store, d)
            assigned_cast = assign_qs.filter(date=d, staff__staff_type='fortune_teller').count()
            assigned_staff = assign_qs.filter(date=d, staff__staff_type='store_staff').count()
            coverage[d.isoformat()] = {
                'fortune_teller': {
                    'required': required.get('fortune_teller', 0),
                    'assigned': assigned_cast,
                },
                'store_staff': {
                    'required': required.get('store_staff', 0),
                    'assigned': assigned_staff,
                },
            }

    return render_to_string('admin/booking/partials/shift_toolbar_grid.html', {
        'staffs': staffs,
        'cast_staffs': cast_staffs,
        'store_staffs': store_staffs,
        'week_dates': week_dates,
        'grid': grid,
        'templates': templates,
        'coverage': coverage,
        'week_start': week_dates[0].isoformat(),
        'prev_week': (week_dates[0] - timedelta(weeks=1)).isoformat(),
        'next_week': (week_dates[0] + timedelta(weeks=1)).isoformat(),
        'prev_month': (week_dates[0] - timedelta(days=28)).isoformat(),
        'next_month': (week_dates[0] + timedelta(days=28)).isoformat(),
        'active_period': active_period,
        'staff_type_filter': staff_type_filter or '',
        'staff_count': len(cast_staffs) + len(store_staffs),
        'cast_count': len(cast_staffs),
        'store_staff_count': len(store_staffs),
    }, request=request)


# ==============================
# 店長向けページ View
# ==============================

class ManagerShiftCalendarView(AdminSidebarMixin, TemplateView):
    """シフトカレンダー表示ページ"""
    template_name = 'admin/booking/shift_calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        staff = getattr(user, 'staff', None)
        store = _get_user_store(self.request)
        week_dates = _get_week_dates(self.request.GET.get('week_start'))

        # ロール判定
        role = getattr(user, '_admin_role', None)
        if not role:
            role = 'staff' if staff and not user.is_superuser and not getattr(staff, 'is_store_manager', False) and not getattr(staff, 'is_owner', False) else 'manager'
        is_staff_role = (role == 'staff')
        ctx['user_role'] = role
        ctx['is_staff_role'] = is_staff_role

        staff_type_filter = self.request.GET.get('staff_type', '')
        all_staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()
        cast_staffs = list(all_staffs.filter(staff_type='fortune_teller'))
        store_staffs = list(all_staffs.filter(staff_type='store_staff'))
        all_staff_count = len(cast_staffs) + len(store_staffs)
        if staff_type_filter == 'fortune_teller':
            staffs = cast_staffs
        elif staff_type_filter == 'store_staff':
            staffs = store_staffs
        else:
            staffs = list(all_staffs)
        staff_count = all_staff_count

        assign_qs = ShiftAssignment.objects.filter(
            period__store=store,
            date__gte=week_dates[0],
            date__lte=week_dates[-1],
        ).select_related('staff', 'period') if store else ShiftAssignment.objects.none()
        if staff_type_filter in ('fortune_teller', 'store_staff'):
            assign_qs = assign_qs.filter(staff__staff_type=staff_type_filter)
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
        submitted_staff_details = []
        if active_period:
            reqs = ShiftRequest.objects.filter(
                period=active_period,
            ).select_related('staff')
            submitted_staff = reqs.values('staff').distinct().count()
            total_requests = reqs.count()
            request_stats = {
                'submitted_staff': submitted_staff,
                'total_requests': total_requests,
            }
            # 提出済みスタッフ別の希望一覧
            if not is_staff_role:
                from collections import defaultdict
                by_staff = defaultdict(list)
                for r in reqs.order_by('staff__name', 'date', 'start_hour'):
                    by_staff[r.staff_id].append(r)
                for staff_id, staff_reqs in by_staff.items():
                    s = staff_reqs[0].staff
                    submitted_staff_details.append({
                        'staff': s,
                        'requests': staff_reqs,
                        'count': len(staff_reqs),
                    })

        grid = {}
        for a in assignments:
            if a.staff_id not in grid:
                grid[a.staff_id] = {}
            grid[a.staff_id][a.date.isoformat()] = a

        publish_history = ShiftPublishHistory.objects.filter(
            period__store=store,
        ).select_related('published_by', 'period').order_by('-published_at')[:5] if store else []

        # 不足枠 & 交代申請
        vacancies = ShiftVacancy.objects.none()
        vacancy_count = 0
        swap_requests = ShiftSwapRequest.objects.none()
        swap_pending_count = 0
        if active_period and not is_staff_role:
            vacancies = ShiftVacancy.objects.filter(
                period=active_period, status='open',
            ).order_by('date', 'start_hour')
            vacancy_count = vacancies.count()
            swap_requests = ShiftSwapRequest.objects.filter(
                assignment__period=active_period, status='pending',
            ).select_related('assignment', 'requested_by', 'cover_staff')
            swap_pending_count = swap_requests.count()

        ctx.update({
            'title': _('シフトカレンダー'),
            'has_permission': True,
            'store': store,
            'stores': Store.objects.all(),
            'staffs': staffs,
            'cast_staffs': cast_staffs,
            'store_staffs': store_staffs,
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
            'prev_month': (week_dates[0] - timedelta(days=28)).isoformat(),
            'next_month': (week_dates[0] + timedelta(days=28)).isoformat(),
            'submitted_staff_details': submitted_staff_details,
            'staff_type_filter': staff_type_filter,
            'cast_count': Staff.objects.filter(store=store, staff_type='fortune_teller').count() if store else 0,
            'store_staff_count': Staff.objects.filter(store=store, staff_type='store_staff').count() if store else 0,
            'vacancies': vacancies,
            'vacancy_count': vacancy_count,
            'swap_requests': swap_requests,
            'swap_pending_count': swap_pending_count,
        })

        # スタッフ用追加コンテキスト
        if is_staff_role and staff:
            open_periods = ShiftPeriod.objects.filter(
                store=store, status='open',
            ).order_by('-year_month')
            my_assignments = ShiftAssignment.objects.filter(
                staff=staff, date__gte=date.today(),
            ).select_related('period').order_by('date', 'start_hour')
            my_requests = ShiftRequest.objects.filter(
                staff=staff, period__status='open',
            ).select_related('period').order_by('date', 'start_hour')
            ctx.update({
                'open_periods': open_periods,
                'my_assignments': my_assignments,
                'my_requests': my_requests,
                'staff_obj': staff,
            })

        return ctx


class TodayShiftTimelineView(AdminSidebarMixin, TemplateView):
    """本日のシフト: 縦軸=時間、横軸=スタッフのタイムライン表示"""
    template_name = 'admin/booking/today_shift.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        today = date.today()

        # ロール別フィルタ: 一般スタッフは自分のシフトのみ表示
        user = self.request.user
        staff_obj = getattr(user, 'staff', None)
        is_regular_staff = (
            staff_obj and not user.is_superuser
            and not staff_obj.is_store_manager
            and not staff_obj.is_owner
            and not staff_obj.is_developer
        )

        if is_regular_staff:
            staffs = [staff_obj]
            assignments = ShiftAssignment.objects.filter(
                staff=staff_obj, date=today,
            ).select_related('staff', 'period')
        elif store:
            staffs = list(Staff.objects.filter(store=store).order_by('name'))
            assignments = ShiftAssignment.objects.filter(
                period__store=store, date=today,
            ).select_related('staff', 'period')
        else:
            staffs = []
            assignments = ShiftAssignment.objects.none()

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

        # 本日の必要人数サマリ
        today_coverage = {}
        if store:
            required = get_required_counts(store, today)
            assigned_cast = assignments.filter(staff__staff_type='fortune_teller').count()
            assigned_staff = assignments.filter(staff__staff_type='store_staff').count()
            today_coverage = {
                'fortune_teller': {
                    'required': required.get('fortune_teller', 0),
                    'assigned': assigned_cast,
                },
                'store_staff': {
                    'required': required.get('store_staff', 0),
                    'assigned': assigned_staff,
                },
            }

        ctx.update({
            'title': _('本日のシフト'),
            'has_permission': True,
            'store': store,
            'today': today,
            'staffs': staffs,
            'hours': hours,
            'staff_shifts': staff_shifts,
            'staff_shifts_json': staff_shifts_json,
            'today_coverage': today_coverage,
        })
        return ctx
