"""シフト管理 API View"""
import json
import logging
import re
from datetime import date, datetime

from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from booking.models import (
    Store, Staff, ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory, ShiftChangeLog,
)
from booking.views_shift_manager import _get_user_store, _render_calendar_section
from booking.validators import (
    validate_hour_range, validate_color, truncate_note,
)
from booking.api_response import success_response, error_response, list_response

logger = logging.getLogger(__name__)


_TIME_RE = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')


def _validate_time_str(val):
    """HH:MM 形式の文字列バリデーション。不正ならNone。"""
    if val and _TIME_RE.match(str(val)):
        return str(val)
    return None


def _parse_body(request):
    """リクエストボディを JSON or POST (form-encoded) から取得"""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # HTMX hx-vals sends form-encoded data
        return {k: v for k, v in request.POST.items()}


def _require_store(request):
    """店舗取得。取得できなければ error_response を返す。"""
    store = _get_user_store(request)
    if store is None:
        return None, error_response('Store not found', status=403)
    return store, None


def _verify_store_ownership(obj_store, user_store):
    """オブジェクトの店舗がユーザーの店舗と一致するか確認"""
    if obj_store.pk != user_store.pk:
        return error_response('Permission denied', status=403)
    return None


# ==============================
# 店長向け API View
# ==============================

@method_decorator(staff_member_required, name='dispatch')
class ShiftWeekGridView(View):
    """HTMX partial: ツールバー + 週グリッドHTML返却"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return HttpResponse('')
        html = _render_calendar_section(
            request, store,
            request.GET.get('week_start'),
            staff_type_filter=request.GET.get('staff_type'),
        )
        return HttpResponse(html)


@method_decorator(staff_member_required, name='dispatch')
class ShiftCellDetailView(View):
    """HTMX partial: サイドバー編集フォーム"""

    def get(self, request, pk):
        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        store = _get_user_store(request)
        if store:
            err = _verify_store_ownership(assignment.period.store, store)
            if err:
                return err
        templates = ShiftTemplate.objects.filter(store=assignment.period.store, is_active=True)

        html = render_to_string('admin/booking/partials/shift_sidebar.html', {
            'assignment': assignment,
            'templates': templates,
        }, request=request)
        return HttpResponse(html)


@method_decorator(staff_member_required, name='dispatch')
class ShiftAssignmentAPIView(View):
    """シフトCRUD API"""

    def post(self, request):
        """新規シフト作成"""
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        period_id = data.get('period_id')
        staff_id = data.get('staff_id')
        date_str = data.get('date')
        template_id = data.get('template_id')

        if not all([period_id, staff_id, date_str]):
            return error_response('Missing required fields')

        start_h, end_h, err = validate_hour_range(data)
        if err:
            return error_response(err)

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)
        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        kwargs = {
            'period': period,
            'staff': staff,
            'date': date_str,
            'start_hour': start_h,
            'end_hour': end_h,
        }

        if template_id:
            template = get_object_or_404(ShiftTemplate, pk=template_id, store=store)
            _apply_template_to_kwargs(kwargs, template)

        if data.get('start_time'):
            validated_time = _validate_time_str(data['start_time'])
            if validated_time:
                kwargs['start_time'] = validated_time
        if data.get('end_time'):
            validated_time = _validate_time_str(data['end_time'])
            if validated_time:
                kwargs['end_time'] = validated_time
        if data.get('color'):
            validated_color = validate_color(data['color'])
            if validated_color:
                kwargs['color'] = validated_color
        if data.get('note'):
            kwargs['note'] = truncate_note(data['note'])

        # 同一スロットに既存シフトがあれば更新、なければ新規作成
        existing = ShiftAssignment.objects.filter(
            period=period, staff=staff, date=date_str, start_hour=start_h,
        ).first()
        if existing:
            for key, val in kwargs.items():
                if key not in ('period', 'staff', 'date', 'start_hour'):
                    setattr(existing, key, val)
            existing.save()
            assignment = existing
            status_code = 200
        else:
            assignment = ShiftAssignment.objects.create(**kwargs)
            status_code = 201

        html = render_to_string('admin/booking/partials/shift_cell.html', {
            'assignment': assignment,
            'date': assignment.date,
            'staff': staff,
        }, request=request)
        return HttpResponse(html, status=status_code)

    def put(self, request, pk=None):
        """シフト更新（approved 期間の場合は変更ログ + Schedule 更新 + 差分通知）"""
        store, err = _require_store(request)
        if err:
            return err

        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        ownership_err = _verify_store_ownership(assignment.period.store, store)
        if ownership_err:
            return ownership_err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        is_approved = assignment.period.status == 'approved'

        if is_approved:
            # approved 期間: revise_assignment で変更ログ付き更新
            reason = data.pop('reason', '')
            new_data = {}

            if 'template_id' in data:
                template = get_object_or_404(ShiftTemplate, pk=data['template_id'], store=store)
                new_data['start_time'] = template.start_time
                new_data['end_time'] = template.end_time
                new_data['color'] = template.color
                new_data['start_hour'] = template.start_time.hour
                new_data['end_hour'] = template.end_time.hour
            else:
                for field in ['start_hour', 'end_hour', 'note', 'start_time', 'end_time']:
                    if field in data:
                        new_data[field] = data[field]
                if 'color' in data:
                    validated_color = validate_color(data['color'])
                    if validated_color:
                        new_data['color'] = validated_color

            revised_by = None
            try:
                revised_by = request.user.staff
            except (Staff.DoesNotExist, AttributeError):
                pass

            old_start = assignment.start_hour
            old_end = assignment.end_hour

            from booking.services.shift_scheduler import revise_assignment
            revise_assignment(assignment, new_data, revised_by=revised_by, reason=reason)

            try:
                from booking.services.shift_notifications import notify_shift_revised
                notify_shift_revised(assignment, {
                    'old_start_hour': old_start,
                    'old_end_hour': old_end,
                })
            except Exception as e:
                logger.warning("Failed to send shift revision notification: %s", e)
        else:
            # 通常の更新（変更ログなし）
            if 'start_hour' in data or 'end_hour' in data:
                merged = {
                    'start_hour': data.get('start_hour', assignment.start_hour),
                    'end_hour': data.get('end_hour', assignment.end_hour),
                }
                s_h, e_h, err = validate_hour_range(merged)
                if err:
                    return error_response(err)
                assignment.start_hour = s_h
                assignment.end_hour = e_h
            if 'note' in data:
                assignment.note = truncate_note(data['note'])
            if 'color' in data:
                validated_color = validate_color(data['color'])
                if validated_color:
                    assignment.color = validated_color
            if 'start_time' in data:
                validated_time = _validate_time_str(data['start_time'])
                if validated_time:
                    assignment.start_time = validated_time
            if 'end_time' in data:
                validated_time = _validate_time_str(data['end_time'])
                if validated_time:
                    assignment.end_time = validated_time
            if 'template_id' in data:
                template = get_object_or_404(ShiftTemplate, pk=data['template_id'], store=store)
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
        store, err = _require_store(request)
        if err:
            return err

        assignment = get_object_or_404(ShiftAssignment, pk=pk)
        ownership_err = _verify_store_ownership(assignment.period.store, store)
        if ownership_err:
            return ownership_err

        assignment.delete()
        return HttpResponse('', status=204)


def _apply_template_to_kwargs(kwargs, template):
    """テンプレートの値をkwargsに適用（DRY共通ヘルパー）"""
    kwargs['start_time'] = template.start_time
    kwargs['end_time'] = template.end_time
    kwargs['color'] = template.color
    kwargs['start_hour'] = template.start_time.hour
    kwargs['end_hour'] = template.end_time.hour


@method_decorator(staff_member_required, name='dispatch')
class ShiftApplyTemplateAPIView(View):
    """テンプレートをセルに適用"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        template = get_object_or_404(ShiftTemplate, pk=data.get('template_id'), store=store)
        staff = get_object_or_404(Staff, pk=data.get('staff_id'), store=store)
        date_str = data.get('date')

        if not date_str:
            return error_response('Missing date')

        period = ShiftPeriod.objects.filter(
            store=store, status__in=['open', 'scheduled'],
        ).order_by('-year_month').first()

        if not period:
            return error_response('No active shift period')

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


@method_decorator(staff_member_required, name='dispatch')
class ShiftTemplateAPIView(View):
    """テンプレートCRUD"""

    def get(self, request):
        store, err = _require_store(request)
        if err:
            return err

        templates = ShiftTemplate.objects.filter(store=store, is_active=True)
        results = [{
            'id': t.id,
            'name': t.name,
            'start_time': t.start_time.strftime('%H:%M'),
            'end_time': t.end_time.strftime('%H:%M'),
            'color': t.color,
        } for t in templates]
        return success_response(results)

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        color = validate_color(data.get('color', '')) or '#3B82F6'
        template = ShiftTemplate.objects.create(
            store=store,
            name=data.get('name', ''),
            start_time=data.get('start_time', '09:00'),
            end_time=data.get('end_time', '17:00'),
            color=color,
        )
        return success_response({'id': template.id, 'name': template.name}, status=201)

    def put(self, request, pk=None):
        store, err = _require_store(request)
        if err:
            return err

        template = get_object_or_404(ShiftTemplate, pk=pk)
        ownership_err = _verify_store_ownership(template.store, store)
        if ownership_err:
            return ownership_err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        for f in ['name', 'start_time', 'end_time']:
            if f in data:
                setattr(template, f, data[f])
        if 'color' in data:
            validated_color = validate_color(data['color'])
            if validated_color:
                template.color = validated_color
        template.save()
        return success_response({'id': template.id, 'name': template.name})

    def delete(self, request, pk=None):
        store, err = _require_store(request)
        if err:
            return err

        template = get_object_or_404(ShiftTemplate, pk=pk)
        ownership_err = _verify_store_ownership(template.store, store)
        if ownership_err:
            return ownership_err

        template.is_active = False
        template.save()
        return HttpResponse('', status=204)


@method_decorator(staff_member_required, name='dispatch')
class ShiftBulkAssignAPIView(View):
    """テンプレートから一括シフト作成"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        template_id = data.get('template_id')
        staff_ids = data.get('staff_ids', [])
        dates = data.get('dates', [])
        period_id = data.get('period_id')

        template = get_object_or_404(ShiftTemplate, pk=template_id, store=store)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        # 事前に全スタッフを一括取得（N+1回避）
        staff_map = {
            s.pk: s
            for s in Staff.objects.filter(pk__in=staff_ids, store=store)
        }

        created = 0
        with transaction.atomic():
            for staff_id in staff_ids:
                staff = staff_map.get(staff_id)
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

        return success_response({'created': created})


@method_decorator(staff_member_required, name='dispatch')
class ShiftAutoScheduleAPIView(View):
    """自動スケジューリング実行"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        data = _parse_body(request)
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
            return error_response('No shift period found', status=404)

        if period.status == 'approved':
            return error_response(
                '承認済みの期間は自動スケジューリングできません。先に取消してください。',
            )

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(period)

        vacancy_count = period.vacancies.filter(status='open').count()

        if request.headers.get('HX-Request'):
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return success_response({
            'created': count,
            'period_id': period.id,
            'vacancy_count': vacancy_count,
        })


@method_decorator(staff_member_required, name='dispatch')
class ShiftPublishAPIView(View):
    """シフト公開（Schedule同期 + LINE通知 + 公開履歴作成）"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        data = _parse_body(request)

        period_id = data.get('period_id')
        note = truncate_note(data.get('note', ''))

        if period_id:
            period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)
        else:
            period = ShiftPeriod.objects.filter(
                store=store, status__in=['open', 'scheduled'],
            ).order_by('-year_month').first()

        if not period:
            return error_response('No shift period found', status=404)

        from booking.services.shift_scheduler import sync_assignments_to_schedule
        from booking.services.shift_notifications import notify_shift_approved

        with transaction.atomic():
            synced = sync_assignments_to_schedule(period)

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

        # SNS自動投稿: シフト公開をトリガー
        try:
            from booking.tasks import task_post_shift_published
            transaction.on_commit(lambda: task_post_shift_published.delay(period.id))
        except Exception as e:
            logger.warning("Failed to queue social posting task: %s", e)

        if request.headers.get('HX-Request'):
            # ステータスが変わるので全体リロード
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return success_response({
            'synced': synced,
            'period_id': period.id,
            'status': period.status,
        })



@method_decorator(staff_member_required, name='dispatch')
class ShiftChangeLogAPIView(View):
    """ShiftChangeLog 一覧取得"""

    def get(self, request):
        store, err = _require_store(request)
        if err:
            return err

        period_id = request.GET.get('period_id')
        logs = ShiftChangeLog.objects.filter(
            assignment__period__store=store,
        ).select_related(
            'assignment__staff', 'assignment__period', 'changed_by',
        ).order_by('-changed_at')

        if period_id:
            logs = logs.filter(assignment__period_id=period_id)

        results = [{
            'id': log.id,
            'assignment_id': log.assignment_id,
            'staff_name': log.assignment.staff.name,
            'date': log.assignment.date.isoformat(),
            'change_type': log.change_type,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'changed_by': log.changed_by.name if log.changed_by else None,
            'reason': log.reason,
            'changed_at': log.changed_at.isoformat(),
        } for log in logs[:100]]

        return list_response(results, total=len(results))


# ==============================
# Re-exports from split modules
# ==============================
from .views_shift_period_api import (  # noqa: F401, E402
    ShiftPeriodAPIView,
    ShiftRevokeAPIView,
    ShiftReopenAPIView,
    StoreClosedDateAPIView,
)
from .views_shift_vacancy_api import (  # noqa: F401, E402
    ShiftVacancyAPIView,
    ShiftVacancyApplyAPIView,
    ShiftSwapRequestAPIView,
)
