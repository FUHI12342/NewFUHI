"""QR勤怠View + API"""
import json
import logging
import base64
from io import BytesIO
from datetime import date, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _

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
            'title': _('QR勤怠'),
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
            staff_status[s.id] = {'staff': s, 'status': _('未出勤'), 'stamps': []}
        for stamp in stamps_today:
            if stamp.staff_id in staff_status:
                staff_status[stamp.staff_id]['stamps'].append(stamp)
                if stamp.stamp_type == 'clock_in':
                    staff_status[stamp.staff_id]['status'] = _('出勤中')
                elif stamp.stamp_type == 'clock_out':
                    staff_status[stamp.staff_id]['status'] = _('退勤済')
                elif stamp.stamp_type == 'break_start':
                    staff_status[stamp.staff_id]['status'] = _('休憩中')
                elif stamp.stamp_type == 'break_end':
                    staff_status[stamp.staff_id]['status'] = _('出勤中')

        # ステータス別にグループ分け
        zone_working = []
        zone_break = []
        zone_absent = []
        zone_left = []
        for info in staff_status.values():
            if info['status'] == _('出勤中'):
                zone_working.append(info)
            elif info['status'] == _('休憩中'):
                zone_break.append(info)
            elif info['status'] == _('退勤済'):
                zone_left.append(info)
            else:
                zone_absent.append(info)

        ctx.update({
            'title': _('出退勤ボード'),
            'has_permission': True,
            'store': store,
            'staff_status': staff_status,
            'zone_working': zone_working,
            'zone_break': zone_break,
            'zone_absent': zone_absent,
            'zone_left': zone_left,
            'today': today,
        })
        return ctx


class AttendanceStampAPIView(LoginRequiredMixin, View):
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
            return JsonResponse({'error': _('5分以内に同一打刻があります')}, status=400)

        # ジオフェンスチェック
        if config and config.require_geo_check and latitude and longitude:
            if config.location_lat and config.location_lng:
                from booking.services.totp_service import check_geo_fence
                if not check_geo_fence(
                    config.location_lat, config.location_lng,
                    float(latitude), float(longitude),
                    config.geo_fence_radius_m,
                ):
                    return JsonResponse({'error': _('店舗の範囲外です')}, status=400)

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
        attendance, _created = WorkAttendance.objects.get_or_create(
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


class AttendanceTOTPRefreshAPI(LoginRequiredMixin, View):
    """現在のTOTP QR画像をHTML fragmentで返す（HTMX対応）"""

    def get(self, request):
        store = _get_user_store(request)
        try:
            config = store.totp_config
        except (AttendanceTOTPConfig.DoesNotExist, AttributeError):
            return HttpResponse(
                '<p style="color:red;">' + _('TOTP未設定です') + '</p>', status=404,
            )

        from booking.services.totp_service import get_current_totp
        code = get_current_totp(config.totp_secret, config.totp_interval)

        # スタンプページURLをQRに埋め込む
        stamp_url = request.build_absolute_uri(
            f'/attendance/stamp/?code={code}&store_id={store.id}'
        )

        # QR画像生成
        try:
            import qrcode
            qr = qrcode.make(stamp_url)
            buf = BytesIO()
            qr.save(buf, format='PNG')
            img_b64 = base64.b64encode(buf.getvalue()).decode()
        except ImportError:
            img_b64 = ''

        # HTML fragment返却（HTMX hx-swap="innerHTML" 対応）
        if img_b64:
            html = (
                f'<img src="data:image/png;base64,{img_b64}" '
                f'class="qr-image" alt="QR">'
                f'<div class="qr-code-text">{code}</div>'
            )
        else:
            html = f'<div class="qr-code-text">{code}</div>'
        return HttpResponse(html)


class AttendancePINDisplayView(AdminSidebarMixin, TemplateView):
    """タイムカード打刻キオスク画面"""
    template_name = 'admin/booking/attendance_pin.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        staffs = Staff.objects.filter(store=store).order_by('name') if store else Staff.objects.none()
        ctx.update({
            'title': _('タイムカード打刻'),
            'has_permission': True,
            'store': store,
            'staffs': staffs,
        })
        return ctx


@method_decorator(csrf_exempt, name='dispatch')
class AttendancePINStampAPIView(LoginRequiredMixin, View):
    """PIN検証 → 打刻API（CSRF免除: PIN認証で保護）"""

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

        # PIN検証（ハッシュ照合、旧平文データにも後方互換）
        if not staff.attendance_pin:
            return JsonResponse({'error': _('PINが未設定です')}, status=400)
        if not staff.check_attendance_pin(pin):
            return JsonResponse({'error': _('PINが正しくありません')}, status=400)

        # 重複チェック
        from booking.services.totp_service import check_duplicate_stamp
        if check_duplicate_stamp(staff_id, stamp_type, minutes=5):
            return JsonResponse({'error': _('5分以内に同一打刻があります')}, status=400)

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
                    return JsonResponse({'error': _('店舗の範囲外です')}, status=400)

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
        attendance, _created = WorkAttendance.objects.get_or_create(
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


class AttendanceDayStatusAPI(LoginRequiredMixin, View):
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
                    'status': _('未出勤'),
                    'stamps': [],
                }
            result[sid]['stamps'].append({
                'type': stamp.stamp_type,
                'at': stamp.stamped_at.isoformat(),
            })
            if stamp.stamp_type == 'clock_in':
                result[sid]['status'] = _('出勤中')
            elif stamp.stamp_type == 'clock_out':
                result[sid]['status'] = _('退勤済')

        return JsonResponse(list(result.values()), safe=False)


class AttendanceStampPageView(View):
    """QRスキャン後のスマホ打刻ページ（ログイン不要）"""

    def get(self, request):
        store_id = request.GET.get('store_id')
        code = request.GET.get('code', '')

        if not store_id:
            return HttpResponse('store_id is required', status=400)

        store = get_object_or_404(Store, pk=store_id)
        staffs = Staff.objects.filter(store=store).order_by('name')

        from django.template.loader import render_to_string
        html = render_to_string('booking/attendance_stamp.html', {
            'store': store,
            'staffs': staffs,
            'totp_code': code,
        }, request=request)
        return HttpResponse(html)


@method_decorator(csrf_exempt, name='dispatch')
class QRStampAPIView(View):
    """QRスキャン打刻API（ログイン不要、TOTP+PINで認証）"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store_id = data.get('store_id')
        staff_id = data.get('staff_id')
        totp_code = data.get('totp_code', '')
        pin = data.get('pin', '')
        stamp_type = data.get('stamp_type', 'clock_in')

        if not store_id:
            return JsonResponse({'error': 'store_id required'}, status=400)
        if not staff_id:
            return JsonResponse({'error': 'staff_id required'}, status=400)
        if not totp_code:
            return JsonResponse({'error': 'totp_code required'}, status=400)
        if not pin:
            return JsonResponse({'error': 'PIN required'}, status=400)

        store = get_object_or_404(Store, pk=store_id)
        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        # TOTP検証
        try:
            config = store.totp_config
        except AttendanceTOTPConfig.DoesNotExist:
            return JsonResponse({'error': _('TOTP未設定です')}, status=400)

        from booking.services.totp_service import verify_totp
        if not verify_totp(config.totp_secret, totp_code, config.totp_interval):
            return JsonResponse({'error': _('QRコードの有効期限切れです。再スキャンしてください')}, status=400)

        # PIN検証
        if not staff.attendance_pin:
            return JsonResponse({'error': _('PINが未設定です')}, status=400)
        if not staff.check_attendance_pin(pin):
            return JsonResponse({'error': _('PINが正しくありません')}, status=400)

        # 重複チェック
        from booking.services.totp_service import check_duplicate_stamp
        if check_duplicate_stamp(staff_id, stamp_type, minutes=5):
            return JsonResponse({'error': _('5分以内に同一打刻があります')}, status=400)

        # ジオフェンスチェック
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if config.require_geo_check and latitude and longitude:
            if config.location_lat and config.location_lng:
                from booking.services.totp_service import check_geo_fence
                if not check_geo_fence(
                    config.location_lat, config.location_lng,
                    float(latitude), float(longitude),
                    config.geo_fence_radius_m,
                ):
                    return JsonResponse({'error': _('店舗の範囲外です')}, status=400)

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
        attendance, _created = WorkAttendance.objects.get_or_create(
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


class ManualStampAPIView(View):
    """管理者によるマニュアル打刻API（端末忘れ時用、ログイン必須）"""

    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': _('ログインが必要です')}, status=403)
        if not (request.user.is_staff or request.user.is_superuser):
            return JsonResponse({'error': _('権限がありません')}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        staff_id = data.get('staff_id')
        stamp_type = data.get('stamp_type', 'clock_in')
        memo = data.get('memo', '')

        if not staff_id:
            return JsonResponse({'error': 'staff_id required'}, status=400)

        staff = get_object_or_404(Staff, pk=staff_id, store=store)

        # 重複チェック
        from booking.services.totp_service import check_duplicate_stamp
        if check_duplicate_stamp(staff_id, stamp_type, minutes=5):
            return JsonResponse({'error': _('5分以内に同一打刻があります')}, status=400)

        # 打刻記録
        ip = request.META.get('REMOTE_ADDR', '')
        ua = request.META.get('HTTP_USER_AGENT', '')

        stamp = AttendanceStamp.objects.create(
            staff=staff,
            stamp_type=stamp_type,
            totp_used='',
            ip_address=ip,
            user_agent=f'manual:{request.user.username} {ua}',
        )

        # WorkAttendance更新
        today = date.today()
        now = timezone.now()
        attendance, _created = WorkAttendance.objects.get_or_create(
            staff=staff,
            date=today,
            defaults={'source': 'manual'},
        )

        if stamp_type == 'clock_in':
            attendance.qr_clock_in = now
            attendance.clock_in = now.time()
            attendance.source = 'manual'
            attendance.save(update_fields=['qr_clock_in', 'clock_in', 'source'])
        elif stamp_type == 'clock_out':
            attendance.qr_clock_out = now
            attendance.clock_out = now.time()
            attendance.source = 'manual'
            attendance.save(update_fields=['qr_clock_out', 'clock_out', 'source'])

        return JsonResponse({
            'success': True,
            'stamp_id': stamp.id,
            'staff_name': staff.name,
            'stamp_type': stamp_type,
            'stamped_at': stamp.stamped_at.isoformat(),
            'operator': request.user.username,
        })
