"""スタッフ向けシフト API"""
import datetime
import json
import logging

from django.http import HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

from booking.models import (
    Staff, ShiftPeriod, ShiftRequest,
)
from booking.views import get_or_create_shift_period
from booking.validators import (
    validate_hour_range, validate_preference, validate_min_shift,
    validate_closed_date,
)
from booking.api_response import success_response, error_response

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class StaffShiftRequestAPIView(View):
    """スタッフ自身のシフト希望CRUD（manager以上は代理操作可）"""

    def _is_manager(self, request, own_staff):
        """manager以上の権限チェック"""
        return (
            own_staff.is_store_manager
            or own_staff.is_owner
            or own_staff.is_developer
            or request.user.is_superuser
        )

    def _get_staff(self, request, body_data=None):
        """対象スタッフを取得。staff_id指定時はmanager以上のみ代理操作可。"""
        own_staff = getattr(request.user, 'staff', None)
        if not own_staff:
            return None, error_response('Staff not found', status=403)

        staff_id = request.GET.get('staff_id')
        if not staff_id and body_data:
            staff_id = body_data.get('staff_id')

        if not staff_id:
            return own_staff, None

        if not self._is_manager(request, own_staff):
            return None, error_response('Permission denied', status=403)

        target = Staff.objects.filter(
            pk=staff_id, store=own_staff.store,
        ).first()
        if not target:
            return None, error_response('Staff not found in your store', status=404)
        return target, None

    def get(self, request):
        staff, err = self._get_staff(request)
        if err:
            return err

        period_id = request.GET.get('period_id')
        qs = ShiftRequest.objects.filter(staff=staff)
        if period_id:
            qs = qs.filter(period_id=period_id)
        else:
            qs = qs.filter(period__status='open')

        results = [{
            'id': r.id,
            'period_id': r.period_id,
            'date': r.date.isoformat(),
            'start_hour': r.start_hour,
            'end_hour': r.end_hour,
            'preference': r.preference,
            'note': r.note,
        } for r in qs.order_by('date', 'start_hour')]
        return success_response(results)

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        staff, err = self._get_staff(request, body_data=data)
        if err:
            return err

        period_id = data.get('period_id')
        date_str = data.get('date')
        preference = data.get('preference', 'available')

        if not all([date_str, data.get('start_hour') is not None, data.get('end_hour') is not None]):
            return error_response('Missing required fields')

        start_h, end_h, hour_err = validate_hour_range(data)
        if hour_err:
            return error_response(hour_err)

        pref_err = validate_preference(preference)
        if pref_err:
            return error_response(pref_err)

        store = staff.store

        try:
            check_date = datetime.date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return error_response('Invalid date format')

        closed_err = validate_closed_date(store, check_date)
        if closed_err:
            return error_response(closed_err)

        _, min_shift_err = validate_min_shift(store, start_h, end_h, preference)
        if min_shift_err:
            return error_response(min_shift_err)

        # period_id指定があればそれを使い、なければ日付から自動作成
        if period_id:
            period = ShiftPeriod.objects.filter(pk=period_id, store=store).first()
            if not period:
                return error_response('期間が見つかりません', status=404)
        else:
            period = get_or_create_shift_period(store, check_date.year, check_date.month, staff=staff)

        shift_req, created = ShiftRequest.objects.update_or_create(
            period=period,
            staff=staff,
            date=date_str,
            start_hour=start_h,
            defaults={
                'end_hour': end_h,
                'preference': preference,
                'note': data.get('note', ''),
            },
        )

        shift_req.refresh_from_db()

        return success_response({
            'id': shift_req.id,
            'date': shift_req.date.isoformat(),
            'start_hour': shift_req.start_hour,
            'end_hour': shift_req.end_hour,
            'preference': shift_req.preference,
        }, status=201 if created else 200)

    def delete(self, request, pk=None):
        staff, err = self._get_staff(request)
        if err:
            return err

        shift_req = ShiftRequest.objects.filter(
            pk=pk, staff=staff,
        ).first()
        if not shift_req:
            return error_response('Not found or not yours', status=404)

        shift_req.delete()
        return HttpResponse('', status=204)
