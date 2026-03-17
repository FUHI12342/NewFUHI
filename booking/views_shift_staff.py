"""スタッフ向けシフト API"""
import json
import logging

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

from booking.models import (
    Staff, ShiftPeriod, ShiftRequest,
)

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
            return None, JsonResponse({'error': 'Staff not found'}, status=403)

        staff_id = request.GET.get('staff_id')
        if not staff_id and body_data:
            staff_id = body_data.get('staff_id')

        if not staff_id:
            return own_staff, None

        if not self._is_manager(request, own_staff):
            return None, JsonResponse(
                {'error': 'Permission denied'}, status=403,
            )

        target = Staff.objects.filter(
            pk=staff_id, store=own_staff.store,
        ).first()
        if not target:
            return None, JsonResponse(
                {'error': 'Staff not found in your store'}, status=404,
            )
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

        data = [{
            'id': r.id,
            'period_id': r.period_id,
            'date': r.date.isoformat(),
            'start_hour': r.start_hour,
            'end_hour': r.end_hour,
            'preference': r.preference,
            'note': r.note,
        } for r in qs.order_by('date', 'start_hour')]
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        staff, err = self._get_staff(request, body_data=data)
        if err:
            return err

        period_id = data.get('period_id')
        date_str = data.get('date')
        start_hour = data.get('start_hour')
        end_hour = data.get('end_hour')
        preference = data.get('preference', 'available')

        if not all([period_id, date_str, start_hour is not None, end_hour is not None]):
            return JsonResponse({'error': 'Missing required fields'}, status=400)

        # バリデーション: start_hour/end_hour 範囲チェック
        try:
            start_h = int(start_hour)
            end_h = int(end_hour)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid hour values'}, status=400)

        if not (0 <= start_h <= 23 and 0 <= end_h <= 24 and start_h < end_h):
            return JsonResponse({'error': 'Invalid hour range'}, status=400)

        store = staff.store
        period = ShiftPeriod.objects.filter(
            pk=period_id, store=store, status='open',
        ).first()
        if not period:
            return JsonResponse({'error': '募集中の期間が見つかりません'}, status=404)

        if preference not in ('available', 'preferred', 'unavailable'):
            return JsonResponse({'error': 'Invalid preference'}, status=400)

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

        return JsonResponse({
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
            return JsonResponse({'error': 'Not found or not yours'}, status=404)

        shift_req.delete()
        return HttpResponse('', status=204)
