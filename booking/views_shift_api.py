"""シフト管理 API View"""
import json
import logging
from datetime import date, datetime

from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from booking.models import (
    Store, Staff, ShiftPeriod, ShiftRequest, ShiftAssignment,
    ShiftTemplate, ShiftPublishHistory, ShiftChangeLog, StoreClosedDate,
    ShiftVacancy, ShiftSwapRequest,
)
from booking.views_shift_manager import _get_user_store, _render_week_grid, _render_calendar_section

logger = logging.getLogger(__name__)


def _parse_body(request):
    """リクエストボディを JSON or POST (form-encoded) から取得"""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        # HTMX hx-vals sends form-encoded data
        return {k: v for k, v in request.POST.items()}


def _require_store(request):
    """店舗取得。取得できなければ JsonResponse を返す。"""
    store = _get_user_store(request)
    if store is None:
        return None, JsonResponse({'error': 'Store not found'}, status=403)
    return store, None


def _verify_store_ownership(obj_store, user_store):
    """オブジェクトの店舗がユーザーの店舗と一致するか確認"""
    if obj_store.pk != user_store.pk:
        return JsonResponse({'error': 'Permission denied'}, status=403)
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
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

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
            _apply_template_to_kwargs(kwargs, template)

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
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

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
                for field in ['start_hour', 'end_hour', 'color', 'note', 'start_time', 'end_time']:
                    if field in data:
                        new_data[field] = data[field]

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
            for field in ['start_hour', 'end_hour', 'color', 'note']:
                if field in data:
                    setattr(assignment, field, data[field])
            if 'start_time' in data:
                assignment.start_time = data['start_time']
            if 'end_time' in data:
                assignment.end_time = data['end_time']
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
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        template = get_object_or_404(ShiftTemplate, pk=data.get('template_id'), store=store)
        staff = get_object_or_404(Staff, pk=data.get('staff_id'), store=store)
        date_str = data.get('date')

        if not date_str:
            return JsonResponse({'error': 'Missing date'}, status=400)

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


@method_decorator(staff_member_required, name='dispatch')
class ShiftTemplateAPIView(View):
    """テンプレートCRUD"""

    def get(self, request):
        store, err = _require_store(request)
        if err:
            return err

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
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        template = ShiftTemplate.objects.create(
            store=store,
            name=data.get('name', ''),
            start_time=data.get('start_time', '09:00'),
            end_time=data.get('end_time', '17:00'),
            color=data.get('color', '#3B82F6'),
        )
        return JsonResponse({'id': template.id, 'name': template.name}, status=201)

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
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        for f in ['name', 'start_time', 'end_time', 'color']:
            if f in data:
                setattr(template, f, data[f])
        template.save()
        return JsonResponse({'id': template.id, 'name': template.name})

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
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

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

        return JsonResponse({'created': created})


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
            return JsonResponse({'error': 'No shift period found'}, status=404)

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(period)

        vacancy_count = period.vacancies.filter(status='open').count()

        if request.headers.get('HX-Request'):
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return JsonResponse({
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

        if request.headers.get('HX-Request'):
            # ステータスが変わるので全体リロード
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return JsonResponse({
            'synced': synced,
            'period_id': period.id,
            'status': period.status,
        })


@method_decorator(staff_member_required, name='dispatch')
class ShiftPeriodAPIView(View):
    """シフト期間 作成・ステータス変更API"""

    def post(self, request):
        """新規シフト期間を作成し、募集を開始"""
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        year_month = data.get('year_month')
        deadline = data.get('deadline')

        if not year_month:
            return JsonResponse({'error': 'year_month is required'}, status=400)

        existing = ShiftPeriod.objects.filter(store=store, year_month=year_month).first()
        if existing:
            return JsonResponse({'error': f'{year_month} の期間は既に存在します', 'period_id': existing.id}, status=409)

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

        try:
            from booking.services.shift_notifications import notify_shift_period_open
            notify_shift_period_open(period)
        except Exception as e:
            logger.warning("Failed to send period open notification: %s", e)

        if request.headers.get('HX-Request'):
            html = render_to_string(
                'admin/booking/partials/period_created_alert.html',
                {'period': period}, request=request,
            )
            return HttpResponse(html, headers={'HX-Trigger': 'periodCreated'})
        return JsonResponse({'id': period.id, 'status': period.status}, status=201)

    def put(self, request, pk=None):
        """シフト期間のステータスを更新"""
        store, err = _require_store(request)
        if err:
            return err

        period = get_object_or_404(ShiftPeriod, pk=pk, store=store)

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


@method_decorator(staff_member_required, name='dispatch')
class ShiftRevokeAPIView(View):
    """シフトの撤回（approved → scheduled, scheduled → open）"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        data = _parse_body(request)

        period_id = data.get('period_id')
        reason = data.get('reason', '')

        if not period_id:
            return JsonResponse({'error': 'period_id is required'}, status=400)

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        if period.status not in ('approved', 'scheduled'):
            return JsonResponse({
                'error': '撤回は公開済み(approved)またはスケジュール済み(scheduled)状態でのみ可能です',
            }, status=400)

        revoked_by = None
        try:
            revoked_by = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        if period.status == 'approved':
            from booking.services.shift_scheduler import revoke_published_shifts
            cancelled = revoke_published_shifts(
                period, reason=reason, revoked_by=revoked_by,
            )
            try:
                from booking.services.shift_notifications import notify_shift_revoked
                notify_shift_revoked(period, reason=reason)
            except Exception as e:
                logger.warning("Failed to send revoke notification: %s", e)
        else:
            # scheduled → open: アサインメント削除してopen に戻す
            from booking.services.shift_scheduler import revert_scheduled
            cancelled = revert_scheduled(
                period, reason=reason, reverted_by=revoked_by,
            )

        if request.headers.get('HX-Request'):
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return JsonResponse({
            'cancelled': cancelled,
            'period_id': period.id,
            'status': period.status,
        })


@method_decorator(staff_member_required, name='dispatch')
class ShiftReopenAPIView(View):
    """スケジュール済みシフトの再募集（アサインメント保持のままopenに戻す）"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        data = _parse_body(request)
        period_id = data.get('period_id')
        reason = data.get('reason', '')

        if not period_id:
            return JsonResponse({'error': 'period_id is required'}, status=400)

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        if period.status != 'scheduled':
            return JsonResponse({
                'error': '再募集はスケジュール済み(scheduled)状態でのみ可能です',
            }, status=400)

        reopened_by = None
        try:
            reopened_by = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        from booking.services.shift_scheduler import reopen_for_recruitment
        kept = reopen_for_recruitment(
            period, reason=reason, reopened_by=reopened_by,
        )

        if request.headers.get('HX-Request'):
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return JsonResponse({
            'kept_assignments': kept,
            'period_id': period.id,
            'status': period.status,
        })


@method_decorator(staff_member_required, name='dispatch')
class StoreClosedDateAPIView(View):
    """休業日トグルAPI: GET で月別一覧、POST で追加/削除トグル"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return JsonResponse([], safe=False)

        year = request.GET.get('year', str(date.today().year))
        month = request.GET.get('month', str(date.today().month))
        try:
            y, m = int(year), int(month)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid year/month'}, status=400)

        from calendar import monthrange
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])

        closed = StoreClosedDate.objects.filter(
            store=store, date__gte=start, date__lte=end,
        ).order_by('date')

        data = [
            {'id': c.id, 'date': c.date.isoformat(), 'reason': c.reason}
            for c in closed
        ]
        return JsonResponse(data, safe=False)

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        date_str = data.get('date')
        if not date_str:
            return JsonResponse({'error': 'date is required'}, status=400)

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)

        reason = data.get('reason', '')

        existing = StoreClosedDate.objects.filter(store=store, date=target_date).first()
        if existing:
            existing.delete()
            return JsonResponse({'action': 'removed', 'date': date_str})

        StoreClosedDate.objects.create(store=store, date=target_date, reason=reason)
        return JsonResponse({'action': 'added', 'date': date_str}, status=201)


# ==============================
# 不足枠 (Vacancy) API
# ==============================

@method_decorator(staff_member_required, name='dispatch')
class ShiftVacancyAPIView(View):
    """不足枠一覧（管理者・スタッフ共通）"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return JsonResponse([], safe=False)

        qs = ShiftVacancy.objects.filter(store=store, status='open')

        period_id = request.GET.get('period_id')
        if period_id:
            qs = qs.filter(period_id=period_id)

        staff_type = request.GET.get('staff_type')
        if staff_type:
            qs = qs.filter(staff_type=staff_type)

        data = [{
            'id': v.id,
            'period_id': v.period_id,
            'date': v.date.isoformat(),
            'start_hour': v.start_hour,
            'end_hour': v.end_hour,
            'staff_type': v.staff_type,
            'required_count': v.required_count,
            'assigned_count': v.assigned_count,
            'shortage': v.shortage,
            'status': v.status,
        } for v in qs.order_by('date', 'start_hour')]
        return JsonResponse(data, safe=False)


@method_decorator(staff_member_required, name='dispatch')
class ShiftVacancyApplyAPIView(View):
    """不足枠への応募（スタッフがShiftRequestを作成）"""

    def post(self, request, pk):
        vacancy = get_object_or_404(ShiftVacancy, pk=pk)

        try:
            staff = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            return JsonResponse({'error': 'Staff not found'}, status=403)

        if vacancy.store_id != staff.store_id:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        if vacancy.status != 'open':
            return JsonResponse({'error': 'この不足枠は既に締切済みです'}, status=400)

        if staff.staff_type != vacancy.staff_type:
            return JsonResponse({'error': 'スタッフ種別が一致しません'}, status=400)

        existing = ShiftRequest.objects.filter(
            period=vacancy.period,
            staff=staff,
            date=vacancy.date,
            start_hour=vacancy.start_hour,
        ).first()
        if existing:
            return JsonResponse({'error': 'この日時は既に応募済みです'}, status=409)

        shift_req = ShiftRequest.objects.create(
            period=vacancy.period,
            staff=staff,
            date=vacancy.date,
            start_hour=vacancy.start_hour,
            end_hour=vacancy.end_hour,
            preference='preferred',
            note=f'不足枠応募 (vacancy #{vacancy.id})',
        )

        return JsonResponse({
            'id': shift_req.id,
            'date': shift_req.date.isoformat(),
            'start_hour': shift_req.start_hour,
            'end_hour': shift_req.end_hour,
        }, status=201)


# ==============================
# 交代・欠勤申請 (SwapRequest) API
# ==============================

@method_decorator(staff_member_required, name='dispatch')
class ShiftSwapRequestAPIView(View):
    """交代・欠勤申請の一覧取得・作成・承認/却下"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return JsonResponse([], safe=False)

        qs = ShiftSwapRequest.objects.filter(
            assignment__period__store=store,
        ).select_related('assignment', 'requested_by', 'cover_staff')

        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        period_id = request.GET.get('period_id')
        if period_id:
            qs = qs.filter(assignment__period_id=period_id)

        data = [{
            'id': sr.id,
            'assignment_id': sr.assignment_id,
            'assignment_date': sr.assignment.date.isoformat(),
            'assignment_start': sr.assignment.start_hour,
            'assignment_end': sr.assignment.end_hour,
            'request_type': sr.request_type,
            'requested_by': sr.requested_by.name,
            'cover_staff': sr.cover_staff.name if sr.cover_staff else None,
            'reason': sr.reason,
            'status': sr.status,
            'created_at': sr.created_at.isoformat(),
        } for sr in qs[:50]]
        return JsonResponse(data, safe=False)

    def post(self, request):
        """新規申請作成"""
        try:
            staff = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            return JsonResponse({'error': 'Staff not found'}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        assignment_id = data.get('assignment_id')
        request_type = data.get('request_type')
        reason = data.get('reason', '')
        cover_staff_id = data.get('cover_staff_id')

        if not assignment_id or not request_type:
            return JsonResponse({'error': 'assignment_id and request_type are required'}, status=400)

        if request_type not in ('swap', 'cover', 'absence'):
            return JsonResponse({'error': 'Invalid request_type'}, status=400)

        assignment = get_object_or_404(ShiftAssignment, pk=assignment_id)
        if assignment.staff_id != staff.id and not staff.is_store_manager:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        cover_staff = None
        if cover_staff_id:
            cover_staff = get_object_or_404(Staff, pk=cover_staff_id, store=staff.store)

        swap_req = ShiftSwapRequest.objects.create(
            assignment=assignment,
            request_type=request_type,
            requested_by=staff,
            cover_staff=cover_staff,
            reason=reason,
        )

        try:
            from booking.services.shift_notifications import notify_swap_request
            notify_swap_request(swap_req)
        except Exception as e:
            logger.warning("Failed to send swap request notification: %s", e)

        return JsonResponse({
            'id': swap_req.id,
            'status': swap_req.status,
        }, status=201)

    def put(self, request, pk=None):
        """管理者による承認/却下"""
        store, err = _require_store(request)
        if err:
            return err

        swap_req = get_object_or_404(ShiftSwapRequest, pk=pk)

        if swap_req.assignment.period.store_id != store.id:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        new_status = data.get('status')
        if new_status not in ('approved', 'rejected', 'cancelled'):
            return JsonResponse({'error': 'Invalid status'}, status=400)

        if swap_req.status != 'pending':
            return JsonResponse({'error': '既に処理済みです'}, status=400)

        reviewer = None
        try:
            reviewer = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        swap_req.status = new_status
        swap_req.reviewed_by = reviewer
        swap_req.reviewed_at = timezone.now()
        swap_req.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        if new_status == 'approved':
            _process_approved_swap(swap_req)

        try:
            from booking.services.shift_notifications import notify_swap_approved
            notify_swap_approved(swap_req)
        except Exception as e:
            logger.warning("Failed to send swap approval notification: %s", e)

        return JsonResponse({
            'id': swap_req.id,
            'status': swap_req.status,
        })


def _process_approved_swap(swap_req):
    """承認されたSwapRequestの後処理"""
    assignment = swap_req.assignment

    if swap_req.request_type == 'absence':
        # 欠勤: アサインメント削除 + 不足枠生成 + カバー募集通知
        vacancy = ShiftVacancy.objects.create(
            period=assignment.period,
            store=assignment.period.store,
            date=assignment.date,
            start_hour=assignment.start_hour,
            end_hour=assignment.end_hour,
            staff_type=assignment.staff.staff_type,
            required_count=1,
            assigned_count=0,
            status='open',
        )
        assignment.delete()

        try:
            from booking.services.shift_notifications import notify_emergency_cover
            notify_emergency_cover(vacancy)
        except Exception as e:
            logger.warning("Failed to send emergency cover notification: %s", e)

    elif swap_req.request_type in ('swap', 'cover') and swap_req.cover_staff:
        # 交代/カバー: 元のアサインメント削除 + 新アサインメント作成
        new_assignment = ShiftAssignment.objects.create(
            period=assignment.period,
            staff=swap_req.cover_staff,
            date=assignment.date,
            start_hour=assignment.start_hour,
            end_hour=assignment.end_hour,
            start_time=assignment.start_time,
            end_time=assignment.end_time,
            color=assignment.color,
            note=f'交代: {swap_req.requested_by.name} → {swap_req.cover_staff.name}',
        )

        ShiftChangeLog.objects.create(
            assignment=new_assignment,
            changed_by=swap_req.reviewed_by,
            change_type='revised',
            old_values={
                'staff': swap_req.requested_by.name,
                'staff_id': swap_req.requested_by.id,
            },
            new_values={
                'staff': swap_req.cover_staff.name,
                'staff_id': swap_req.cover_staff.id,
            },
            reason=f'{swap_req.get_request_type_display()}: {swap_req.reason}',
        )
        assignment.delete()
