"""Shift period management API views:
ShiftPeriodAPIView, ShiftRevokeAPIView, ShiftReopenAPIView,
StoreClosedDateAPIView."""
import json
import logging
from datetime import date, datetime

from django.http import HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from booking.models import (
    Staff, ShiftPeriod, StoreClosedDate,
)
from booking.views_shift_manager import _get_user_store
from booking.api_response import success_response, error_response

logger = logging.getLogger(__name__)


def _parse_body(request):
    """リクエストボディを JSON or POST (form-encoded) から取得"""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {k: v for k, v in request.POST.items()}


def _require_store(request):
    """店舗取得。取得できなければ error_response を返す。"""
    store = _get_user_store(request)
    if store is None:
        return None, error_response('Store not found', status=403)
    return store, None


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
            return error_response('Invalid JSON')

        year_month = data.get('year_month')
        deadline = data.get('deadline')

        if not year_month:
            return error_response('year_month is required')

        existing = ShiftPeriod.objects.filter(store=store, year_month=year_month).first()
        if existing:
            return error_response(
                f'{year_month} の期間は既に存在します', status=409,
            )

        created_by = None
        try:
            created_by = request.user.staff
        except (Staff.DoesNotExist, AttributeError):
            pass

        parsed_deadline = None
        if deadline:
            from django.utils.dateparse import parse_datetime, parse_date
            from django.utils import timezone as tz
            dt = parse_datetime(deadline)
            if dt is None:
                d = parse_date(deadline)
                if d:
                    dt = datetime.datetime.combine(d, datetime.time.min)
            if dt and tz.is_naive(dt):
                dt = tz.make_aware(dt)
            parsed_deadline = dt

        period = ShiftPeriod.objects.create(
            store=store,
            year_month=year_month,
            deadline=parsed_deadline,
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
        return success_response({'id': period.id, 'status': period.status}, status=201)

    def put(self, request, pk=None):
        """シフト期間のステータスを更新"""
        store, err = _require_store(request)
        if err:
            return err

        period = get_object_or_404(ShiftPeriod, pk=pk, store=store)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        new_status = data.get('status')
        valid_transitions = {
            'open': ['closed'],
            'closed': ['open', 'scheduled'],
            'scheduled': ['open', 'approved'],
            'approved': ['scheduled'],
        }
        if new_status not in valid_transitions.get(period.status, []):
            return error_response(
                f'{period.get_status_display()} -> {new_status} への遷移は無効です',
            )

        period.status = new_status
        if data.get('deadline'):
            period.deadline = data['deadline']
        period.save()

        return success_response({'id': period.id, 'status': period.status})


@method_decorator(staff_member_required, name='dispatch')
class ShiftRevokeAPIView(View):
    """シフトの撤回（approved -> scheduled, scheduled -> open）"""

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        data = _parse_body(request)

        period_id = data.get('period_id')
        reason = data.get('reason', '')

        if not period_id:
            return error_response('period_id is required')

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        if period.status not in ('approved', 'scheduled'):
            return error_response(
                '撤回は公開済み(approved)またはスケジュール済み(scheduled)状態でのみ可能です',
            )

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
            # scheduled -> open: アサインメント削除してopen に戻す
            from booking.services.shift_scheduler import revert_scheduled
            cancelled = revert_scheduled(
                period, reason=reason, reverted_by=revoked_by,
            )

        if request.headers.get('HX-Request'):
            return HttpResponse(
                '', headers={'HX-Redirect': f'/admin/shift/calendar/?period_id={period.id}'},
            )
        return success_response({
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
            return error_response('period_id is required')

        period = get_object_or_404(ShiftPeriod, pk=period_id, store=store)

        if period.status != 'scheduled':
            return error_response(
                '再募集はスケジュール済み(scheduled)状態でのみ可能です',
            )

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
        return success_response({
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
            return success_response([])

        year = request.GET.get('year', str(date.today().year))
        month = request.GET.get('month', str(date.today().month))
        try:
            y, m = int(year), int(month)
        except (ValueError, TypeError):
            return error_response('Invalid year/month')

        from calendar import monthrange
        start = date(y, m, 1)
        end = date(y, m, monthrange(y, m)[1])

        closed = StoreClosedDate.objects.filter(
            store=store, date__gte=start, date__lte=end,
        ).order_by('date')

        results = [
            {'id': c.id, 'date': c.date.isoformat(), 'reason': c.reason}
            for c in closed
        ]
        return success_response(results)

    def post(self, request):
        store, err = _require_store(request)
        if err:
            return err

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        date_str = data.get('date')
        if not date_str:
            return error_response('date is required')

        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return error_response('Invalid date format')

        reason = data.get('reason', '')

        existing = StoreClosedDate.objects.filter(store=store, date=target_date).first()
        if existing:
            existing.delete()
            return success_response({'action': 'removed', 'date': date_str})

        StoreClosedDate.objects.create(store=store, date=target_date, reason=reason)
        return success_response({'action': 'added', 'date': date_str}, status=201)
