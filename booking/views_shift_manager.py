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
from django.utils.translation import gettext as _

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import (
    Store, Staff, ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory, StoreScheduleConfig,
)

logger = logging.getLogger(__name__)


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
        staff_count = staffs.count()

        # 該当週のシフト（期間指定がある場合はその期間のみ）
        assign_qs = ShiftAssignment.objects.filter(
            period__store=store,
            date__gte=week_dates[0],
            date__lte=week_dates[-1],
        ).select_related('staff', 'period') if store else ShiftAssignment.objects.none()
        assignments = assign_qs

        # テンプレート一覧
        templates = ShiftTemplate.objects.filter(store=store, is_active=True) if store else ShiftTemplate.objects.none()

        # シフト期間一覧
        periods = ShiftPeriod.objects.filter(store=store).order_by('-year_month') if store else ShiftPeriod.objects.none()

        # アクティブ期間（URLパラメータ or 最新のopen/scheduled期間）
        period_id = self.request.GET.get('period_id')
        if period_id:
            active_period = periods.filter(pk=period_id).first()
        else:
            active_period = periods.filter(status__in=['open', 'scheduled']).first()
        if not active_period:
            active_period = periods.first()

        # 期間ごとのリクエスト集計
        request_stats = {}
        if active_period:
            reqs = ShiftRequest.objects.filter(period=active_period)
            submitted_staff = reqs.values('staff').distinct().count()
            total_requests = reqs.count()
            request_stats = {
                'submitted_staff': submitted_staff,
                'total_requests': total_requests,
            }

        # セルデータ構築: {staff_id: {date_str: assignment}}
        grid = {}
        for a in assignments:
            if a.staff_id not in grid:
                grid[a.staff_id] = {}
            grid[a.staff_id][a.date.isoformat()] = a

        # 公開履歴（最新5件）
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


class ShiftWeekGridView(View):
    """HTMX partial: 週グリッドHTML返却"""

    def get(self, request):
        store = _get_user_store(request)
        html = _render_week_grid(request, store, request.GET.get('week_start'))
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
            if request.headers.get('HX-Request'):
                return HttpResponse('<p style="color:#EF4444;padding:16px;">シフト期間が見つかりません</p>')
            return JsonResponse({'error': 'No shift period found'}, status=404)

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(period)

        # HTMX: 週グリッドHTMLを返す
        if request.headers.get('HX-Request'):
            html = _render_week_grid(request, store, request.GET.get('week_start'))
            return HttpResponse(html)
        return JsonResponse({'created': count, 'period_id': period.id})


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

        # 時間スロット: 9:00〜23:00
        hours = list(range(9, 24))

        # スタッフごとのシフトマップ
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

        # JSON for JS rendering
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

        # HTMX: 週グリッドHTMLを返す
        if request.headers.get('HX-Request'):
            html = _render_week_grid(request, store, request.GET.get('week_start'))
            return HttpResponse(html)
        return JsonResponse({
            'synced': synced,
            'period_id': period.id,
            'status': period.status,
        })


class ShiftPeriodAPIView(View):
    """シフト期間 作成・ステータス変更API"""

    def post(self, request):
        """新規シフト期間を作成し、募集を開始"""
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        year_month = data.get('year_month')
        deadline = data.get('deadline')

        if not year_month:
            return JsonResponse({'error': 'year_month is required'}, status=400)

        # 既存チェック
        existing = ShiftPeriod.objects.filter(store=store, year_month=year_month).first()
        if existing:
            return JsonResponse({'error': f'{year_month} の期間は既に存在します', 'period_id': existing.id}, status=409)

        # 作成者の取得
        created_by = None
        try:
            created_by = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        period = ShiftPeriod.objects.create(
            store=store,
            year_month=year_month,
            deadline=deadline or None,
            status='open',
            created_by=created_by,
        )

        # 募集開始通知を送信
        try:
            from booking.services.shift_notifications import notify_shift_period_open
            notify_shift_period_open(period)
        except Exception as e:
            logger.warning("Failed to send period open notification: %s", e)

        if request.headers.get('HX-Request'):
            return HttpResponse(
                f'<div class="alert-success" style="padding:12px;background:#d1fae5;color:#065f46;'
                f'border-radius:6px;margin:8px 0;">'
                f'{period.year_month.strftime("%Y年%m月")} のシフト募集を開始しました。'
                f'スタッフに通知を送信しました。</div>',
                headers={'HX-Trigger': 'periodCreated'},
            )
        return JsonResponse({'id': period.id, 'status': period.status}, status=201)

    def put(self, request, pk=None):
        """シフト期間のステータスを更新"""
        period = get_object_or_404(ShiftPeriod, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        new_status = data.get('status')
        valid_transitions = {
            'open': ['closed'],
            'closed': ['open', 'scheduled'],
            'scheduled': ['open', 'approved'],
            'approved': ['scheduled'],
        }
        if new_status not in valid_transitions.get(period.status, []):
            return JsonResponse({
                'error': f'{period.get_status_display()} → {new_status} への遷移は無効です',
            }, status=400)

        period.status = new_status
        if data.get('deadline'):
            period.deadline = data['deadline']
        period.save()

        return JsonResponse({'id': period.id, 'status': period.status})
