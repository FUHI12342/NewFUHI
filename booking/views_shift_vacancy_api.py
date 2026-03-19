"""Shift vacancy and swap request API views:
ShiftVacancyAPIView, ShiftVacancyApplyAPIView, ShiftSwapRequestAPIView."""
import json
import logging

from django.db import transaction
from django.views import View
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404

from booking.models import (
    Staff, ShiftRequest, ShiftAssignment,
    ShiftChangeLog, ShiftVacancy, ShiftSwapRequest,
)
from booking.views_shift_manager import _get_user_store
from booking.validators import truncate_note
from booking.api_response import success_response, error_response, list_response

logger = logging.getLogger(__name__)


def _require_store(request):
    """店舗取得。取得できなければ error_response を返す。"""
    store = _get_user_store(request)
    if store is None:
        return None, error_response('Store not found', status=403)
    return store, None


@method_decorator(staff_member_required, name='dispatch')
class ShiftVacancyAPIView(View):
    """不足枠一覧（管理者・スタッフ共通）"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return list_response([], total=0)

        qs = ShiftVacancy.objects.filter(store=store, status='open')

        period_id = request.GET.get('period_id')
        if period_id:
            try:
                period_id = int(period_id)
            except (ValueError, TypeError):
                return error_response('Invalid period_id')
            qs = qs.filter(period_id=period_id)

        staff_type = request.GET.get('staff_type')
        if staff_type:
            qs = qs.filter(staff_type=staff_type)

        qs = qs.order_by('date', 'start_hour')

        # pagination (default: 100件)
        try:
            limit = min(int(request.GET.get('limit', 100)), 500)
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (ValueError, TypeError):
            limit, offset = 100, 0

        total = qs.count()
        results = [{
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
        } for v in qs[offset:offset + limit]]
        return list_response(results, total=total, limit=limit)


@method_decorator(staff_member_required, name='dispatch')
class ShiftVacancyApplyAPIView(View):
    """不足枠への応募（スタッフがShiftRequestを作成）"""

    def post(self, request, pk):
        try:
            staff = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            return error_response('Staff not found', status=403)

        with transaction.atomic():
            vacancy = get_object_or_404(
                ShiftVacancy.objects.select_for_update(), pk=pk,
            )

            if vacancy.store_id != staff.store_id:
                return error_response('Permission denied', status=403)

            if vacancy.status != 'open':
                return error_response('この不足枠は既に締切済みです')

            if staff.staff_type != vacancy.staff_type:
                return error_response('スタッフ種別が一致しません')

            existing = ShiftRequest.objects.filter(
                period=vacancy.period,
                staff=staff,
                date=vacancy.date,
                start_hour=vacancy.start_hour,
            ).exists()
            if existing:
                return error_response('この日時は既に応募済みです', status=409)

            shift_req = ShiftRequest.objects.create(
                period=vacancy.period,
                staff=staff,
                date=vacancy.date,
                start_hour=vacancy.start_hour,
                end_hour=vacancy.end_hour,
                preference='preferred',
                note=f'不足枠応募 (vacancy #{vacancy.id})',
            )

            # 応募後の充足チェック
            assigned_count = ShiftAssignment.objects.filter(
                period=vacancy.period,
                date=vacancy.date,
                start_hour__lt=vacancy.end_hour,
                end_hour__gt=vacancy.start_hour,
                staff__staff_type=vacancy.staff_type,
            ).count()
            if assigned_count >= vacancy.required_count:
                vacancy.status = 'filled'
                vacancy.assigned_count = assigned_count
                vacancy.save(update_fields=['status', 'assigned_count'])

        return success_response({
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
            return list_response([], total=0)

        qs = ShiftSwapRequest.objects.filter(
            assignment__period__store=store,
        ).select_related('assignment', 'requested_by', 'cover_staff')

        # 一般スタッフは自分の申請のみ閲覧可能
        staff = getattr(request.user, 'staff', None)
        if staff and not (
            staff.is_store_manager or staff.is_owner
            or staff.is_developer or request.user.is_superuser
        ):
            qs = qs.filter(requested_by=staff)

        status_filter = request.GET.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        period_id = request.GET.get('period_id')
        if period_id:
            try:
                period_id = int(period_id)
            except (ValueError, TypeError):
                return error_response('Invalid period_id')
            qs = qs.filter(assignment__period_id=period_id)

        qs = qs.order_by('-created_at')

        # pagination
        try:
            limit = min(int(request.GET.get('limit', 100)), 500)
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (ValueError, TypeError):
            limit, offset = 100, 0

        total = qs.count()
        results = [{
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
        } for sr in qs[offset:offset + limit]]
        return list_response(results, total=total, limit=limit)

    def post(self, request):
        """新規申請作成"""
        try:
            staff = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            return error_response('Staff not found', status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        assignment_id = data.get('assignment_id')
        request_type = data.get('request_type')
        reason = truncate_note(data.get('reason', ''))
        cover_staff_id = data.get('cover_staff_id')

        if not assignment_id or not request_type:
            return error_response('assignment_id and request_type are required')

        if request_type not in ('swap', 'cover', 'absence'):
            return error_response('Invalid request_type')

        assignment = get_object_or_404(
            ShiftAssignment.objects.select_related('period'),
            pk=assignment_id,
        )
        if assignment.period.store_id != staff.store_id:
            return error_response('Permission denied', status=403)
        if assignment.staff_id != staff.id and not staff.is_store_manager:
            return error_response('Permission denied', status=403)

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

        return success_response({
            'id': swap_req.id,
            'status': swap_req.status,
        }, status=201)

    def put(self, request, pk=None):
        """管理者による承認/却下"""
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        new_status = data.get('status')
        if new_status not in ('approved', 'rejected', 'cancelled'):
            return error_response('Invalid status')

        reviewer = None
        try:
            reviewer = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        # マネージャー権限チェック
        if not reviewer or not (
            reviewer.is_store_manager or reviewer.is_owner
            or reviewer.is_developer or request.user.is_superuser
        ):
            return error_response('承認/却下にはマネージャー権限が必要です', status=403)

        with transaction.atomic():
            swap_req = get_object_or_404(
                ShiftSwapRequest.objects.select_for_update()
                .select_related(
                    'assignment__period__store',
                    'assignment__staff',
                    'requested_by',
                    'cover_staff',
                ),
                pk=pk,
            )

            if swap_req.assignment.period.store_id != store.id:
                return error_response('Permission denied', status=403)

            if swap_req.status != 'pending':
                return error_response('既に処理済みです')

            # 交代先スタッフのスケジュール競合チェック
            if new_status == 'approved' and swap_req.cover_staff:
                conflict = ShiftAssignment.objects.filter(
                    period=swap_req.assignment.period,
                    staff=swap_req.cover_staff,
                    date=swap_req.assignment.date,
                    start_hour__lt=swap_req.assignment.end_hour,
                    end_hour__gt=swap_req.assignment.start_hour,
                ).exists()
                if conflict:
                    return error_response(
                        '交代先スタッフは同日時に既にシフトが割り当てられています',
                        status=409, code='SCHEDULE_CONFLICT',
                    )

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

        return success_response({
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
            note=f'交代: {swap_req.requested_by.name} -> {swap_req.cover_staff.name}',
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
