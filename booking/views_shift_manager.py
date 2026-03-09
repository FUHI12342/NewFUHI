"""シフトカレンダー管理View + API"""
import json
import logging
from datetime import date, timedelta, time, datetime

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import (
    Store, Staff, ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory, StoreScheduleConfig,
)

logger = logging.getLogger(__name__)


def _get_user_store(request):
    """リクエストユーザーの店舗を取得"""
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


def _get_week_dates(week_start_str=None):
    """週の開始日から7日分のリストを返す"""
    if week_start_str:
        try:
            start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        except ValueError:
            start = date.today()
    else:
        start = date.today()
    # 月曜始まり
    start = start - timedelta(days=start.weekday())
    return [start + timedelta(days=i) for i in range(7)]


class ManagerShiftCalendarView(AdminSidebarMixin, TemplateView):
    """シフトカレンダー表示ページ"""
    template_name = 'admin/booking/shift_calendar.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        week_dates = _get_week_dates(self.request.GET.get('week_start'))

        # スタッフ一覧
        staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()

        # 該当週のシフト
        assignments = ShiftAssignment.objects.filter(
            period__store=store,
            date__gte=week_dates[0],
            date__lte=week_dates[-1],
        ).select_related('staff', 'period') if store else ShiftAssignment.objects.none()

        # テンプレート一覧
        templates = ShiftTemplate.objects.filter(store=store, is_active=True) if store else ShiftTemplate.objects.none()

        # シフト期間一覧
        periods = ShiftPeriod.objects.filter(store=store).order_by('-year_month') if store else ShiftPeriod.objects.none()

        # セルデータ構築: {staff_id: {date_str: assignment}}
        grid = {}
        for a in assignments:
            if a.staff_id not in grid:
                grid[a.staff_id] = {}
            grid[a.staff_id][a.date.isoformat()] = a

        ctx.update({
            'title': 'シフトカレンダー',
            'has_permission': True,
            'store': store,
            'stores': Store.objects.all(),
            'staffs': staffs,
            'week_dates': week_dates,
            'grid': grid,
            'templates': templates,
            'periods': periods,
            'week_start': week_dates[0].isoformat(),
            'prev_week': (week_dates[0] - timedelta(weeks=1)).isoformat(),
            'next_week': (week_dates[0] + timedelta(weeks=1)).isoformat(),
        })
        return ctx


class ShiftWeekGridView(View):
    """HTMX partial: 週グリッドHTML返却"""

    def get(self, request):
        store = _get_user_store(request)
        week_dates = _get_week_dates(request.GET.get('week_start'))
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

        html = render_to_string('admin/booking/partials/shift_week_grid.html', {
            'staffs': staffs,
            'week_dates': week_dates,
            'grid': grid,
            'templates': templates,
            'week_start': week_dates[0].isoformat(),
            'prev_week': (week_dates[0] - timedelta(weeks=1)).isoformat(),
            'next_week': (week_dates[0] + timedelta(weeks=1)).isoformat(),
        }, request=request)
        return HttpResponse(html)


class ShiftCellDetailView(View):
    """HTMX partial: サイドバー編集フォーム"""

    def get(self, request, pk):
        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        store = assignment.period.store
        templates = ShiftTemplate.objects.filter(store=store, is_active=True)

        html = render_to_string('admin/booking/partials/shift_sidebar.html', {
            'assignment': assignment,
            'templates': templates,
        }, request=request)
        return HttpResponse(html)


class ShiftAssignmentAPIView(View):
    """シフトCRUD API"""

    def post(self, request):
        """新規シフト作成"""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        period_id = data.get('period_id')
        staff_id = data.get('staff_id')
        date_str = data.get('date')
        start_hour = data.get('start_hour', 9)
        end_hour = data.get('end_hour', 17)
        template_id = data.get('template_id')

        if not all([period_id, staff_id, date_str]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)
        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        kwargs = {
            'period': period,
            'staff': staff,
            'date': date_str,
            'start_hour': int(start_hour),
            'end_hour': int(end_hour),
        }

        if template_id:
            template = get_object_or_404(ShiftTemplate, pk=template_id, store=store)
            kwargs['start_time'] = template.start_time
            kwargs['end_time'] = template.end_time
            kwargs['color'] = template.color
            kwargs['start_hour'] = template.start_time.hour
            kwargs['end_hour'] = template.end_time.hour

        if data.get('start_time'):
            kwargs['start_time'] = data['start_time']
        if data.get('end_time'):
            kwargs['end_time'] = data['end_time']
        if data.get('color'):
            kwargs['color'] = data['color']
        if data.get('note'):
            kwargs['note'] = data['note']

        assignment = ShiftAssignment.objects.create(**kwargs)

        html = render_to_string('admin/booking/partials/shift_cell.html', {
            'assignment': assignment,
            'date': assignment.date,
            'staff': staff,
        }, request=request)
        return HttpResponse(html, status=201)

    def put(self, request, pk=None):
        """シフト更新"""
        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        for field in ['start_hour', 'end_hour', 'color', 'note']:
            if field in data:
                setattr(assignment, field, data[field])
        if 'start_time' in data:
            assignment.start_time = data['start_time']
        if 'end_time' in data:
            assignment.end_time = data['end_time']
        if 'template_id' in data:
            template = get_object_or_404(ShiftTemplate, pk=data['template_id'])
            assignment.start_time = template.start_time
            assignment.end_time = template.end_time
            assignment.color = template.color
            assignment.start_hour = template.start_time.hour
            assignment.end_hour = template.end_time.hour

        assignment.save()

        html = render_to_string('admin/booking/partials/shift_cell.html', {
            'assignment': assignment,
            'date': assignment.date,
            'staff': assignment.staff,
        }, request=request)
        return HttpResponse(html)

    def delete(self, request, pk=None):
        """シフト削除"""
        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        assignment.delete()
        return HttpResponse('', status=204)


class ShiftApplyTemplateAPIView(View):
    """テンプレートをセルに適用"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        template = get_object_or_404(ShiftTemplate, pk=data.get('template_id'), store=store)
        staff = get_object_or_404(Staff, pk=data.get('staff_id'), store=store)
        date_str = data.get('date')

        if not date_str:
            return JsonResponse({'error': 'Missing date'}, status=400)

        # 既存のを見つけるか作成
        period = ShiftPeriod.objects.filter(
            store=store, status__in=['open', 'scheduled'],
        ).order_by('-year_month').first()

        if not period:
            return JsonResponse({'error': 'No active shift period'}, status=400)

        assignment, created = ShiftAssignment.objects.update_or_create(
            period=period,
            staff=staff,
            date=date_str,
            start_hour=template.start_time.hour,
            defaults={
                'end_hour': template.end_time.hour,
                'start_time': template.start_time,
                'end_time': template.end_time,
                'color': template.color,
            },
        )

        html = render_to_string('admin/booking/partials/shift_cell.html', {
            'assignment': assignment,
            'date': assignment.date,
            'staff': staff,
        }, request=request)
        return HttpResponse(html, status=201 if created else 200)


class ShiftTemplateAPIView(View):
    """テンプレートCRUD"""

    def get(self, request):
        store = _get_user_store(request)
        templates = ShiftTemplate.objects.filter(store=store, is_active=True)
        data = [{
            'id': t.id,
            'name': t.name,
            'start_time': t.start_time.strftime('%H:%M'),
            'end_time': t.end_time.strftime('%H:%M'),
            'color': t.color,
        } for t in templates]
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        store = _get_user_store(request)
        template = ShiftTemplate.objects.create(
            store=store,
            name=data.get('name', ''),
            start_time=data.get('start_time', '09:00'),
            end_time=data.get('end_time', '17:00'),
            color=data.get('color', '#3B82F6'),
        )
        return JsonResponse({'id': template.id, 'name': template.name}, status=201)

    def put(self, request, pk=None):
        template = get_object_or_404(ShiftTemplate, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        for f in ['name', 'start_time', 'end_time', 'color']:
            if f in data:
                setattr(template, f, data[f])
        template.save()
        return JsonResponse({'id': template.id, 'name': template.name})

    def delete(self, request, pk=None):
        template = get_object_or_404(ShiftTemplate, pk=pk)
        template.is_active = False
        template.save()
        return HttpResponse('', status=204)


class ShiftBulkAssignAPIView(View):
    """テンプレートから一括シフト作成"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        template_id = data.get('template_id')
        staff_ids = data.get('staff_ids', [])
        dates = data.get('dates', [])
        period_id = data.get('period_id')

        template = get_object_or_404(ShiftTemplate, pk=template_id, store=store)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        created = 0
        for staff_id in staff_ids:
            staff = Staff.objects.filter(pk=staff_id, store=store).first()
            if not staff:
                continue
            for d in dates:
                _, was_created = ShiftAssignment.objects.get_or_create(
                    period=period,
                    staff=staff,
                    date=d,
                    start_hour=template.start_time.hour,
                    defaults={
                        'end_hour': template.end_time.hour,
                        'start_time': template.start_time,
                        'end_time': template.end_time,
                        'color': template.color,
                    },
                )
                if was_created:
                    created += 1

        return JsonResponse({'created': created})


class ShiftAutoScheduleAPIView(View):
    """自動スケジューリング実行"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        store = _get_user_store(request)
        period_id = data.get('period_id')

        if period_id:
            period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)
        else:
            period = ShiftPeriod.objects.filter(
                store=store, status__in=['open', 'scheduled'],
            ).order_by('-year_month').first()

        if not period:
            return JsonResponse({'error': 'No shift period found'}, status=404)

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(period)
        return JsonResponse({'created': count, 'period_id': period.id})


class ShiftPublishAPIView(View):
    """シフト公開（Schedule同期 + LINE通知 + 公開履歴作成）"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        store = _get_user_store(request)
        period_id = data.get('period_id')
        note = data.get('note', '')

        if period_id:
            period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)
        else:
            period = ShiftPeriod.objects.filter(
                store=store, status__in=['open', 'scheduled'],
            ).order_by('-year_month').first()

        if not period:
            return JsonResponse({'error': 'No shift period found'}, status=404)

        from booking.services.shift_scheduler import sync_assignments_to_schedule
        from booking.services.shift_notifications import notify_shift_approved

        synced = sync_assignments_to_schedule(period)

        # 公開者の特定
        publisher = None
        try:
            publisher = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        ShiftPublishHistory.objects.create(
            period=period,
            published_by=publisher,
            assignment_count=period.assignments.count(),
            note=note,
        )

        try:
            notify_shift_approved(period)
        except Exception as e:
            logger.warning("Failed to send shift notification: %s", e)

        return JsonResponse({
            'synced': synced,
            'period_id': period.id,
            'status': period.status,
        })
