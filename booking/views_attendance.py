"""QR勤怠View + API"""
import json
import logging
import base64
from io import BytesIO
from datetime import date, timedelta

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.utils import timezone

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import (
    Store, Staff, AttendanceTOTPConfig, AttendanceStamp, WorkAttendance,
)

logger = logging.getLogger(__name__)


def _get_user_store(request):
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


class AttendanceQRDisplayView(AdminSidebarMixin, TemplateView):
    """QRキオスク画面（30秒ごとHTMXでQR更新）"""
    template_name = 'admin/booking/attendance_qr.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        ctx.update({
            'title': 'QR勤怠',
            'has_permission': True,
            'store': store,
        })
        return ctx


class AttendanceBoardView(AdminSidebarMixin, TemplateView):
    """本日の出退勤状況ボード"""
    template_name = 'admin/booking/attendance_board.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        today = date.today()

        staffs = Staff.objects.filter(store=store) if store else Staff.objects.none()
        stamps_today = AttendanceStamp.objects.filter(
            staff__store=store,
            stamped_at__date=today,
            is_valid=True,
        ).select_related('staff').order_by('stamped_at') if store else []

        # スタッフごとのステータス構築
        staff_status = {}
        for s in staffs:
            staff_status[s.id] = {'staff': s, 'status': '未出勤', 'stamps': []}
        for stamp in stamps_today:
            if stamp.staff_id in staff_status:
                staff_status[stamp.staff_id]['stamps'].append(stamp)
                if stamp.stamp_type == 'clock_in':
                    staff_status[stamp.staff_id]['status'] = '出勤中'
                elif stamp.stamp_type == 'clock_out':
                    staff_status[stamp.staff_id]['status'] = '退勤済'
                elif stamp.stamp_type == 'break_start':
                    staff_status[stamp.staff_id]['status'] = '休憩中'
                elif stamp.stamp_type == 'break_end':
                    staff_status[stamp.staff_id]['status'] = '出勤中'

        ctx.update({
            'title': '出退勤ボード',
            'has_permission': True,
            'store': store,
            'staff_status': staff_status,
            'today': today,
        })
        return ctx


class AttendanceStampAPIView(View):
    """TOTP検証 → 打刻API"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        staff_id = data.get('staff_id')
        stamp_type = data.get('stamp_type', 'clock_in')
        totp_code = data.get('totp_code', '')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not staff_id:
            return JsonResponse({'error': 'staff_id required'}, status=400)

        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        # TOTP検証
        try:
            config = store.totp_config
        except AttendanceTOTPConfig.DoesNotExist:
            config = None

        if config and config.is_active and totp_code:
            from booking.services.totp_service import verify_totp
            if not verify_totp(config.totp_secret, totp_code, config.totp_interval):
                return JsonResponse({'error': 'Invalid TOTP code'}, status=400)

        # 重複チェック
        from booking.services.totp_service import check_duplicate_stamp
        if check_duplicate_stamp(staff_id, stamp_type, minutes=5):
            return JsonResponse({'error': '5分以内に同一打刻があります'}, status=400)

        # ジオフェンスチェック
        if config and config.require_geo_check and latitude and longitude:
            if config.location_lat and config.location_lng:
                from booking.services.totp_service import check_geo_fence
                if not check_geo_fence(
                    config.location_lat, config.location_lng,
                    float(latitude), float(longitude),
                    config.geo_fence_radius_m,
                ):
                    return JsonResponse({'error': '店舗の範囲外です'}, status=400)

        # 打刻記録
        ip = request.META.get('REMOTE_ADDR', '')
        ua = request.META.get('HTTP_USER_AGENT', '')

        stamp = AttendanceStamp.objects.create(
            staff=staff,
            stamp_type=stamp_type,
            totp_used=totp_code,
            ip_address=ip,
            user_agent=ua,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
        )

        # WorkAttendance更新
        today = date.today()
        now = timezone.now()
        attendance, _ = WorkAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={'source': 'qr'},
        )

        if stamp_type == 'clock_in':
            attendance.qr_clock_in = now
            attendance.clock_in = now.time()
            attendance.source = 'qr'
            attendance.save(update_fields=['qr_clock_in', 'clock_in', 'source'])
        elif stamp_type == 'clock_out':
            attendance.qr_clock_out = now
            attendance.clock_out = now.time()
            attendance.source = 'qr'
            attendance.save(update_fields=['qr_clock_out', 'clock_out', 'source'])

        return JsonResponse({
            'success': True,
            'stamp_id': stamp.id,
            'staff_name': staff.name,
            'stamp_type': stamp_type,
            'stamped_at': stamp.stamped_at.isoformat(),
        })


class AttendanceTOTPRefreshAPI(View):
    """現在のTOTP QR画像をbase64で返す"""

    def get(self, request):
        store = _get_user_store(request)
        try:
            config = store.totp_config
        except (AttendanceTOTPConfig.DoesNotExist, AttributeError):
            return JsonResponse({'error': 'TOTP not configured'}, status=404)

        from booking.services.totp_service import get_current_totp
        code = get_current_totp(config.totp_secret, config.totp_interval)

        # QR画像生成
        try:
            import qrcode
            qr = qrcode.make(code)
            buf = BytesIO()
            qr.save(buf, format='PNG')
            img_b64 = base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            img_b64 = ''

        return JsonResponse({
            'code': code,
            'image': f'data:image/png;base64,{img_b64}' if img_b64 else '',
            'interval': config.totp_interval,
        })


class AttendancePINDisplayView(AdminSidebarMixin, TemplateView):
    """PIN打刻キオスク画面"""
    template_name = 'admin/booking/attendance_pin.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()
        ctx.update({
            'title': 'PIN打刻',
            'has_permission': True,
            'store': store,
            'staffs': staffs,
        })
        return ctx


class AttendancePINStampAPIView(View):
    """PIN検証 → 打刻API"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        staff_id = data.get('staff_id')
        pin = data.get('pin', '')
        stamp_type = data.get('stamp_type', 'clock_in')
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if not staff_id:
            return JsonResponse({'error': 'staff_id required'}, status=400)
        if not pin:
            return JsonResponse({'error': 'PIN required'}, status=400)

        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        # PIN検証
        if not staff.attendance_pin:
            return JsonResponse({'error': 'PINが未設定です'}, status=400)
        if staff.attendance_pin != pin:
            return JsonResponse({'error': 'PINが正しくありません'}, status=400)

        # 重複チェック
        from booking.services.totp_service import check_duplicate_stamp
        if check_duplicate_stamp(staff_id, stamp_type, minutes=5):
            return JsonResponse({'error': '5分以内に同一打刻があります'}, status=400)

        # ジオフェンスチェック
        try:
            config = store.totp_config
        except AttendanceTOTPConfig.DoesNotExist:
            config = None

        if config and config.require_geo_check and latitude and longitude:
            if config.location_lat and config.location_lng:
                from booking.services.totp_service import check_geo_fence
                if not check_geo_fence(
                    config.location_lat, config.location_lng,
                    float(latitude), float(longitude),
                    config.geo_fence_radius_m,
                ):
                    return JsonResponse({'error': '店舗の範囲外です'}, status=400)

        # 打刻記録
        ip = request.META.get('REMOTE_ADDR', '')
        ua = request.META.get('HTTP_USER_AGENT', '')

        stamp = AttendanceStamp.objects.create(
            staff=staff,
            stamp_type=stamp_type,
            totp_used='',
            ip_address=ip,
            user_agent=ua,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
        )

        # WorkAttendance更新
        today = date.today()
        now = timezone.now()
        attendance, _ = WorkAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={'source': 'pin'},
        )

        if stamp_type == 'clock_in':
            attendance.qr_clock_in = now
            attendance.clock_in = now.time()
            attendance.source = 'pin'
            attendance.save(update_fields=['qr_clock_in', 'clock_in', 'source'])
        elif stamp_type == 'clock_out':
            attendance.qr_clock_out = now
            attendance.clock_out = now.time()
            attendance.source = 'pin'
            attendance.save(update_fields=['qr_clock_out', 'clock_out', 'source'])

        return JsonResponse({
            'success': True,
            'stamp_id': stamp.id,
            'staff_name': staff.name,
            'stamp_type': stamp_type,
            'stamped_at': stamp.stamped_at.isoformat(),
        })


class AttendanceDayStatusAPI(View):
    """本日の出退勤状況JSON"""

    def get(self, request):
        store = _get_user_store(request)
        today = date.today()

        stamps = AttendanceStamp.objects.filter(
            staff__store=store,
            stamped_at__date=today,
            is_valid=True,
        ).select_related('staff').order_by('stamped_at') if store else []

        result = {}
        for stamp in stamps:
            sid = stamp.staff_id
            if sid not in result:
                result[sid] = {
                    'staff_id': sid,
                    'staff_name': stamp.staff.name,
                    'status': '未出勤',
                    'stamps': [],
                }
            result[sid]['stamps'].append({
                'type': stamp.stamp_type,
                'at': stamp.stamped_at.isoformat(),
            })
            if stamp.stamp_type == 'clock_in':
                result[sid]['status'] = '出勤中'
            elif stamp.stamp_type == 'clock_out':
                result[sid]['status'] = '退勤済'

        return JsonResponse(list(result.values()), safe=False)
