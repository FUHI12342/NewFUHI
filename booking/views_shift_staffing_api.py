"""必要人数設定 API — 曜日別デフォルト + 日付指定オーバーライド"""
import json
import logging
from datetime import date

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

from booking.models import ShiftStaffRequirement, ShiftStaffRequirementOverride
from booking.views_shift_manager import _get_user_store
from booking.api_response import success_response, error_response

logger = logging.getLogger(__name__)


def _parse_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {k: v for k, v in request.POST.items()}


# ==============================
# 曜日別デフォルト必要人数
# ==============================

@method_decorator(staff_member_required, name='dispatch')
class StaffingRequirementAPIView(View):
    """GET: 曜日別一覧 / PUT: 曜日別一括保存"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return error_response('Store not found', status=403)

        reqs = ShiftStaffRequirement.objects.filter(store=store)
        data = [
            {
                'id': r.id,
                'day_of_week': r.day_of_week,
                'staff_type': r.staff_type,
                'required_count': r.required_count,
            }
            for r in reqs
        ]
        return success_response(data)

    def put(self, request):
        store = _get_user_store(request)
        if not store:
            return error_response('Store not found', status=403)

        body = _parse_body(request)
        items = body.get('items', [])
        if not isinstance(items, list):
            return error_response('items must be a list')

        results = []
        for item in items:
            day = item.get('day_of_week')
            staff_type = item.get('staff_type')
            count = item.get('required_count')

            if day is None or staff_type is None or count is None:
                continue

            try:
                day = int(day)
                count = int(count)
            except (ValueError, TypeError):
                continue

            if day < 0 or day > 6 or count < 0:
                continue

            if staff_type not in ('fortune_teller', 'store_staff'):
                continue

            obj, created = ShiftStaffRequirement.objects.update_or_create(
                store=store,
                day_of_week=day,
                staff_type=staff_type,
                defaults={'required_count': count},
            )
            results.append({
                'id': obj.id,
                'day_of_week': obj.day_of_week,
                'staff_type': obj.staff_type,
                'required_count': obj.required_count,
            })

        return success_response(results)


# ==============================
# 日付指定オーバーライド
# ==============================

@method_decorator(staff_member_required, name='dispatch')
class StaffingOverrideAPIView(View):
    """GET: 月別一覧 / POST: 追加 / DELETE: 削除"""

    def get(self, request):
        store = _get_user_store(request)
        if not store:
            return error_response('Store not found', status=403)

        year = request.GET.get('year')
        month = request.GET.get('month')

        qs = ShiftStaffRequirementOverride.objects.filter(store=store)
        if year and month:
            try:
                qs = qs.filter(date__year=int(year), date__month=int(month))
            except (ValueError, TypeError):
                pass

        data = [
            {
                'id': r.id,
                'date': r.date.isoformat(),
                'staff_type': r.staff_type,
                'required_count': r.required_count,
                'reason': r.reason,
            }
            for r in qs
        ]
        return success_response(data)

    def post(self, request):
        store = _get_user_store(request)
        if not store:
            return error_response('Store not found', status=403)

        body = _parse_body(request)
        date_str = body.get('date')
        staff_type = body.get('staff_type')
        count = body.get('required_count')
        reason = body.get('reason', '')

        if not date_str or not staff_type or count is None:
            return error_response('date, staff_type, required_count are required')

        try:
            d = date.fromisoformat(date_str)
            count = int(count)
        except (ValueError, TypeError):
            return error_response('Invalid date or count')

        if count < 0:
            return error_response('required_count must be >= 0')

        if staff_type not in ('fortune_teller', 'store_staff'):
            return error_response('Invalid staff_type')

        obj, created = ShiftStaffRequirementOverride.objects.update_or_create(
            store=store,
            date=d,
            staff_type=staff_type,
            defaults={
                'required_count': count,
                'reason': reason[:100],
            },
        )
        return success_response({
            'id': obj.id,
            'date': obj.date.isoformat(),
            'staff_type': obj.staff_type,
            'required_count': obj.required_count,
            'reason': obj.reason,
        }, status=201 if created else 200)

    def delete(self, request, pk=None):
        store = _get_user_store(request)
        if not store:
            return error_response('Store not found', status=403)

        if pk is None:
            return error_response('pk is required', status=400)

        try:
            obj = ShiftStaffRequirementOverride.objects.get(pk=pk, store=store)
        except ShiftStaffRequirementOverride.DoesNotExist:
            return error_response('Not found', status=404)

        obj.delete()
        return success_response({'deleted': pk})
