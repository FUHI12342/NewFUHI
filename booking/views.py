from __future__ import absolute_import, unicode_literals

import datetime
import json
import jwt
import requests
import secrets
from datetime import timedelta
from urllib.parse import quote
import hashlib
import urllib.parse
import pytz
import logging
from booking.admin_site import custom_site
from typing import Optional, Dict, Any, Tuple

from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.db import transaction
from django.http import (
    HttpResponse,
    JsonResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.views import generic, View
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import admin

from rest_framework import generics, status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from django import forms

from booking.models import (
    Store,
    Staff,
    Schedule,
    Timer,
    UserSerializer,
    IoTDevice,
    IoTEvent,
    Media,
    # ===== 追加: 在庫 / 注文 / 入庫QR / 多言語 =====
    Category,
    Product,
    ProductTranslation,
    Order,
    OrderItem,
    StockMovement,
    apply_stock_movement,
    # ===== Round2: シフト管理 =====
    StoreScheduleConfig,
    ShiftPeriod,
    ShiftRequest,
)
from .forms import StaffForm
from linebot import LineBotApi
from linebot.exceptions import LineBotApiError
from linebot.models import TextSendMessage

logger = logging.getLogger(__name__)

User = get_user_model()


# ===== Store Schedule Config Helper =====

def get_time_slots(store):
    """店舗のスケジュール設定に基づいてタイムスロットを生成"""
    try:
        config = store.schedule_config
    except StoreScheduleConfig.DoesNotExist:
        config = None

    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    duration = config.slot_duration if config else 60

    slots = []
    current = open_h * 60  # 分に変換
    while current + duration <= close_h * 60:
        slots.append({
            'hour': current // 60,
            'minute': current % 60,
            'total_minutes': current,
            'label': f"{current // 60}:{current % 60:02d}",
        })
        current += duration
    return slots, open_h, close_h, duration


def get_hour_range(store):
    """店舗の営業時間範囲を(start_hour, end_hour)で返す（既存コードとの互換用）"""
    try:
        config = store.schedule_config
    except StoreScheduleConfig.DoesNotExist:
        config = None
    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    return open_h, close_h


# ===== IoT API Helper Functions =====

def _safe_json_loads(s: str) -> Optional[Any]:
    """Safely parse JSON string, return None if parsing fails."""
    if not isinstance(s, str):
        return None
    try:
        return json.loads(s.strip())
    except (json.JSONDecodeError, ValueError):
        return None


def _as_mapping(value: Any) -> Dict[str, Any]:
    """Convert value to dict if possible, otherwise return empty dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = _safe_json_loads(value)
        if isinstance(parsed, dict):
            return parsed
    return {}


def _normalize_payload(incoming: Any) -> Tuple[Optional[dict], Dict[str, Any]]:
    """
    Normalize payload to (payload_raw_dict, sensors_dict).
    
    Returns:
        payload_raw_dict: Original dict if incoming was dict, None otherwise
        sensors_dict: Sensor data dict extracted from payload
    """
    if incoming is None:
        return None, {}
    
    if isinstance(incoming, dict):
        # Check for nested sensors structure
        if "sensors" in incoming and isinstance(incoming["sensors"], dict):
            return incoming, incoming["sensors"]
        # Use dict as flat sensors
        return incoming, incoming
    
    # Try to parse as JSON string
    parsed = _safe_json_loads(str(incoming))
    if isinstance(parsed, dict):
        if "sensors" in parsed and isinstance(parsed["sensors"], dict):
            return parsed, parsed["sensors"]
        return parsed, parsed
    
    # Fallback: not parseable
    return None, {}


def _pick_value(request_data: Dict[str, Any], sensors_dict: Dict[str, Any], 
                payload_raw_dict: Optional[dict], key: str) -> Any:
    """
    Pick sensor value from multiple sources with proper None handling.
    
    Priority: 1) request_data, 2) sensors_dict, 3) payload_raw_dict
    Uses 'is not None' to properly handle 0.0 values.
    """
    # Priority 1: top-level request data
    if key in request_data:
        value = request_data.get(key)
        if value is not None:
            return value
    
    # Priority 2: sensors dict from nested payload
    if key in sensors_dict:
        value = sensors_dict.get(key)
        if value is not None:
            return value
    
    # Priority 3: payload root (if dict)
    if payload_raw_dict is not None and key in payload_raw_dict:
        value = payload_raw_dict.get(key)
        if value is not None:
            return value
    
    return None


def _to_float_or_none(value: Any) -> Optional[float]:
    """
    Convert value to float, return None if conversion fails.
    Handles 0, 0.0, "0", "0.0" correctly as 0.0.
    """
    if value is None:
        return None
    
    try:
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, str):
            # Handle both "0" and "0.0" formats
            return float(value)
        else:
            return None
    except (ValueError, TypeError):
        return None


class UserList(generics.ListAPIView):
    """ユーザー一覧API — 管理者のみアクセス可能"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]


class LoginRedirectView(View):
    """ログイン後のスマートリダイレクト: is_staff → /admin/, それ以外 → store_list"""
    def get(self, request):
        if request.user.is_authenticated and request.user.is_staff:
            return redirect(reverse('admin:index'))
        return redirect(reverse('booking:store_list'))


class Index(generic.RedirectView):
    pattern_name = 'booking:booking_top'


class HelpView(generic.TemplateView):
    template_name = 'booking/help.html'


def LINETimerView(request, user_id):
    timer, created = Timer.objects.get_or_create(
        user_id=user_id,
        defaults={'start_time': timezone.now()}
    )
    if not created:
        timer.start_time = timezone.now()
        timer.save()

    timer.end_time = timer.start_time + timedelta(minutes=60)
    timer.save()

    context = {'end_time': timer.end_time}
    return render(request, 'booking/timer.html', context)


def get_end_time(request):
    end_time = timezone.now() + timedelta(hours=1)
    return JsonResponse({'time': end_time.isoformat()})


def get_current_time(request):
    return JsonResponse({'time': timezone.now().isoformat()})


def get_reservation_times(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    return JsonResponse({'startTime': schedule.start.isoformat(), 'endTime': schedule.end.isoformat()})


def get_reservation(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk)
    return JsonResponse({'startTime': schedule.start.isoformat(), 'endTime': schedule.end.isoformat()})


class CurrentTimeView(APIView):
    def get(self, request):
        current_time = datetime.datetime.now()
        return Response({"current_time": str(current_time)})


class IoTEventAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        # Header and required field validation
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            return Response({"detail": "X-API-KEY header is required"}, status=status.HTTP_400_BAD_REQUEST)

        device_name = request.data.get("device")
        if not device_name:
            return Response({"detail": "device is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Device resolution (APIキーはハッシュで照合)
        api_key_hash = IoTDevice.hash_api_key(api_key)
        try:
            device = IoTDevice.objects.get(api_key_hash=api_key_hash, external_id=device_name)
        except IoTDevice.DoesNotExist:
            return Response({"detail": "device not found"}, status=status.HTTP_404_NOT_FOUND)

        # Extract event type and payload
        event_type = request.data.get("event_type", "sensor")
        incoming_payload = request.data.get("payload", None)

        # Normalize payload and extract sensor data using helper functions
        payload_raw_dict, sensors_dict = _normalize_payload(incoming_payload)

        # Extract sensor values with proper priority using helper functions
        sensor_keys = ["mq9", "light", "sound", "temp", "hum", "ts"]
        payload_dict = {}
        
        for key in sensor_keys:
            value = _pick_value(request.data, sensors_dict, payload_raw_dict, key)
            payload_dict[key] = value

        # Handle mq9_value alternative field name
        if payload_dict["mq9"] is None:
            mq9_alt = request.data.get("mq9_value")
            if mq9_alt is not None:
                payload_dict["mq9"] = mq9_alt

        # Convert sensor values to appropriate types for database storage
        mq9_value = _to_float_or_none(payload_dict["mq9"])
        light_value = _to_float_or_none(payload_dict.get("light"))
        sound_value = _to_float_or_none(payload_dict.get("sound"))

        # PIR: treat any truthy value as triggered
        pir_raw = _pick_value(request.data, sensors_dict, payload_raw_dict, "pir")
        pir_triggered = None
        if pir_raw is not None:
            pir_triggered = bool(pir_raw)

        # Create IoT event
        evt = IoTEvent.objects.create(
            device=device,
            event_type=event_type,
            payload=json.dumps(payload_dict, ensure_ascii=False),
            mq9_value=mq9_value,
            light_value=light_value,
            sound_value=sound_value,
            pir_triggered=pir_triggered,
        )

        # Update device last seen timestamp
        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])

        return Response({
            "id": evt.id, 
            "device": device.external_id, 
            "event_type": evt.event_type
        }, status=status.HTTP_201_CREATED)


class IoTConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        external_id = request.GET.get('device')
        api_key = request.headers.get('X-API-KEY')

        if not external_id or not api_key:
            return Response({'detail': 'device または X-API-KEY が足りません'}, status=status.HTTP_400_BAD_REQUEST)

        # APIキーをハッシュで照合
        api_key_hash = IoTDevice.hash_api_key(api_key)
        try:
            device = IoTDevice.objects.get(external_id=external_id, api_key_hash=api_key_hash, is_active=True)
        except IoTDevice.DoesNotExist:
            return Response({'detail': '認証失敗'}, status=status.HTTP_403_FORBIDDEN)

        # Ensure mq9_threshold is never null - provide default value
        DEFAULT_MQ9_THRESHOLD = 500
        mq9_threshold = device.mq9_threshold if device.mq9_threshold is not None else DEFAULT_MQ9_THRESHOLD

        # Ensure threshold is positive
        if mq9_threshold <= 0:
            logger.warning(f"IoT device {device.external_id} has invalid threshold {mq9_threshold}, using default")
            mq9_threshold = DEFAULT_MQ9_THRESHOLD

        # Wi-Fiパスワードは暗号化されたものを復号して返す
        wifi_password = device.get_wifi_password() or ''

        return Response({
            'device': device.external_id,
            'wifi': {'ssid': device.wifi_ssid, 'password': wifi_password},
            'mq9_threshold': int(mq9_threshold),
            'alert_enabled': device.alert_enabled,
        })


class IoTMQ9GraphView(LoginRequiredMixin, generic.TemplateView):
    template_name = "booking/iot_mq9_graph.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(custom_site.each_context(self.request))

        device_external_id = self.request.GET.get("device")

        date_str = self.request.GET.get("date")
        if date_str:
            try:
                target_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                target_date = timezone.localdate()
        else:
            target_date = timezone.localdate()

        qs = IoTEvent.objects.filter(mq9_value__isnull=False, created_at__date=target_date)
        if device_external_id:
            qs = qs.filter(device__external_id=device_external_id)
        qs = qs.order_by("created_at")

        labels = [timezone.localtime(ev.created_at).strftime("%H:%M:%S") for ev in qs]
        values = [ev.mq9_value for ev in qs]

        context["labels_json"] = json.dumps(labels, ensure_ascii=False)
        context["values_json"] = json.dumps(values)
        context["labels"] = labels
        context["labels_values"] = list(zip(labels, values))[::-1]

        live_qs = IoTEvent.objects.filter(mq9_value__isnull=False)
        if device_external_id:
            live_qs = live_qs.filter(device__external_id=device_external_id)
        context["live_events"] = live_qs.order_by("-created_at")[:20]

        context["device_external_id"] = device_external_id
        context["target_date"] = target_date
        return context


def _get_line_setting(name):
    """LINE設定値を取得。未設定の場合はエラーを発生させる。"""
    value = getattr(settings, name, None)
    if not value:
        raise ImproperlyConfigured(
            f"settings.{name} が設定されていません。.envファイルを確認してください。"
        )
    return value

LINE_CHANNEL_ID = _get_line_setting('LINE_CHANNEL_ID')
LINE_CHANNEL_SECRET = _get_line_setting('LINE_CHANNEL_SECRET')
REDIRECT_URL = _get_line_setting('LINE_REDIRECT_URL')


class LineEnterView(View):
    def get(self, request):
        state = secrets.token_hex(10)
        request.session['state'] = state

        params = {
            'response_type': 'code',
            'client_id': LINE_CHANNEL_ID,
            'redirect_uri': REDIRECT_URL,
            'state': state,
            'scope': 'openid profile email',
        }
        auth_url = 'https://access.line.me/oauth2/v2.1/authorize?' + urllib.parse.urlencode(params)
        return HttpResponseRedirect(auth_url)


class LineCallbackView(View):
    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')

        if state != request.session.get('state'):
            return HttpResponseBadRequest()

        if code is None:
            return HttpResponse('トークンの取得に失敗しました')

        uri_access_token = "https://api.line.me/oauth2/v2.1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data_params = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URL,
            "client_id": LINE_CHANNEL_ID,
            "client_secret": LINE_CHANNEL_SECRET
        }
        response_post = requests.post(uri_access_token, headers=headers, data=data_params)

        if response_post.status_code != 200:
            print('トークンの取得に失敗しました: ', response_post.status_code, response_post.text)
            return HttpResponse('トークンの取得に失敗しました')

        line_id_token = json.loads(response_post.text)["id_token"]

        user_profile = jwt.decode(
            line_id_token,
            LINE_CHANNEL_SECRET,
            audience=LINE_CHANNEL_ID,
            issuer='https://access.line.me',
            algorithms=['HS256'],
            options={'verify_iat': False}
        )

        customer_name = user_profile.get('name') if user_profile else 'Unknown User'
        hashed_id = hashlib.sha256(user_profile['sub'].encode()).hexdigest()

        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
        user_id = user_profile['sub']

        try:
            profile = line_bot_api.get_profile(user_id)
            user_id = profile.user_id
        except LineBotApiError as e:
            if getattr(e, "status_code", None) == 404:
                try:
                    line_bot_api.push_message(user_id, TextSendMessage(text="Please add our bot as a friend to continue."))
                except Exception:
                    pass
                return HttpResponseBadRequest()
            return HttpResponseBadRequest()

        try:
            from datetime import datetime as dt, timedelta as td
            now = dt.now()
            expired_on = now + td(days=1)
            expired_on_str = expired_on.strftime('%Y-%m-%d')

            temporary_booking = request.session.get('temporary_booking')
            if temporary_booking is None:
                return HttpResponse('仮予約情報がありません')

            schedule = Schedule(
                reservation_number=temporary_booking['reservation_number'],
                start=timezone.make_aware(dt.fromisoformat(temporary_booking['start'])),
                end=timezone.make_aware(dt.fromisoformat(temporary_booking['end'])),
                price=temporary_booking['price'],
                customer_name=customer_name,
                hashed_id=hashed_id,
                staff_id=temporary_booking['staff_id'],
                is_temporary=True,
            )
            schedule.save()

            # ▼ここが重要：生のLINE user_idは保存しない（暗号化+ハッシュで保存）
            try:
                schedule.set_line_user_id(user_id)
                schedule.save(update_fields=["line_user_hash", "line_user_enc"])
            except Exception as e:
                logger.warning("Failed to store encrypted LINE user id: %s", e)

            del request.session['temporary_booking']

            payment_api_url = settings.PAYMENT_API_URL
            headers = {
                'Authorization': 'Bearer ' + settings.PAYMENT_API_KEY,
                'Content-Type': 'application/json'
            }
            reservation_number = schedule.reservation_number
            webhook_url = f"{settings.WEBHOOK_URL_BASE}{reservation_number}/"

            data = {
                "amount": schedule.price,
                "currency": "jpy",
                "locale": "ja_JP",
                "cancelUrl": settings.CANCEL_URL,
                "webhookUrl": webhook_url,
                "method": "creditcard",
                "subject": "ご予約料金",
                "description": "ウェブサイトからの支払い",
                "remarks": "仮予約から15分を過ぎますと自動的にキャンセルとなります。あらかじめご了承ください。",
                "metadata": {"orderId": reservation_number},
                "expiredOn": expired_on_str
            }

            response = requests.post(payment_api_url, headers=headers, data=json.dumps(data))
            payment_url = None
            if response.status_code == 201:
                try:
                    payment_url = response.json()['links']['paymentUrl']
                except ValueError:
                    print("Error decoding JSON")
            else:
                print("HTTP request failed with status code ", response.status_code)
                print("Response body: ", response.content)

            if payment_url is not None:
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(
                        text='こちらのURLから決済を行ってください。決済後に予約が確定します。\n'
                             '15分以内にお支払いがない場合、仮予約は自動キャンセルされます。\n'
                             + payment_url
                    )
                )

        except LineBotApiError as e:
            print("Failed to send message: ", e)

        request.session['profile'] = user_profile
        return render(request, 'booking/line_success.html', {'profile': user_profile})


class PayingSuccessView(View):
    """決済成功処理 — coiney_webhookからのみ呼び出されることを想定"""
    _called_from_webhook = False

    def post(self, request, orderId):
        if not self._called_from_webhook:
            logger.warning('PayingSuccessView: webhookを経由せず直接呼び出されました')
            return JsonResponse({"error": "Forbidden"}, status=403)
        try:
            payment_response = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        return process_payment(payment_response, request, orderId)


class LineSuccessView(View):
    def get(self, request):
        profile = request.session.get('profile')
        return render(request, 'booking/line_success.html', {'profile': profile})


class OnlyStaffMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return staff.user == self.request.user or self.request.user.is_superuser


class OnlyScheduleMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        schedule = get_object_or_404(Schedule, pk=self.kwargs['pk'])
        return schedule.staff.user == self.request.user or self.request.user.is_superuser


class OnlyUserMixin(UserPassesTestMixin):
    raise_exception = True

    def test_func(self):
        return self.kwargs['pk'] == self.request.user.pk or self.request.user.is_superuser


class BookingTopPage(generic.TemplateView):
    """トップページ: 3つの入口 (店舗/占い師/日付)"""
    template_name = 'booking/booking_top.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['stores'] = Store.objects.all().order_by('name')
        return context


class AllFortuneTellerList(generic.ListView):
    """全店舗横断の占い師一覧 (staff_type='fortune_teller' のみ)"""
    model = Staff
    template_name = 'booking/all_fortune_tellers.html'
    context_object_name = 'fortune_tellers'
    ordering = 'name'

    def get_queryset(self):
        return super().get_queryset().filter(
            staff_type='fortune_teller'
        ).select_related('store')


class DateFirstCalendar(generic.TemplateView):
    """日付優先カレンダー: 日付を選ぶ → その日空きのある占い師一覧 (全店舗横断)"""
    template_name = 'booking/date_first_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = datetime.date.today()

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')

        if year and month and day:
            selected_date = datetime.date(year=year, month=month, day=day)
        else:
            selected_date = None

        # 14日分のカレンダー
        calendar_days = [today + datetime.timedelta(days=d) for d in range(14)]
        context['calendar_days'] = calendar_days
        context['selected_date'] = selected_date
        context['today'] = today

        if selected_date:
            # 全占い師のスケジュールをバルク取得して N+1 回避
            fortune_tellers = Staff.objects.filter(
                staff_type='fortune_teller'
            ).select_related('store')

            # 選択日の既存予約を一括取得
            booked = Schedule.objects.filter(
                staff__staff_type='fortune_teller',
                start__date=selected_date,
                is_cancelled=False,
            ).values_list('staff_id', 'start')

            booked_set = set()
            for staff_id, start in booked:
                local_dt = timezone.localtime(start) if timezone.is_aware(start) else start
                booked_set.add((staff_id, local_dt.hour, local_dt.minute))

            available_tellers = []
            for teller in fortune_tellers:
                time_slots, open_h, close_h, duration = get_time_slots(teller.store)
                free_slots = []
                for slot in time_slots:
                    if (teller.id, slot['hour'], slot['minute']) not in booked_set:
                        free_slots.append(slot)
                if free_slots:
                    available_tellers.append({
                        'staff': teller,
                        'free_slots': free_slots,
                    })

            context['available_tellers'] = available_tellers

            # 祝日コンテキスト
            context['public_holidays'] = settings.PUBLIC_HOLIDAYS

        return context


class StoreList(generic.ListView):
    model = Store
    ordering = 'name'


class StaffList(generic.ListView):
    model = Staff
    ordering = 'name'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['store'] = self.store
        return context

    def get_queryset(self):
        self.store = get_object_or_404(Store, pk=self.kwargs['pk'])
        return super().get_queryset().filter(store=self.store, staff_type='fortune_teller')


class StaffCalendar(generic.TemplateView):
    template_name = 'booking/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        today = datetime.date.today()

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        base_date = datetime.date(year=year, month=month, day=day) if (year and month and day) else today

        days = [base_date + datetime.timedelta(days=d) for d in range(7)]
        start_day = days[0]
        end_day = days[-1]

        # 動的タイムスロット
        time_slots, open_h, close_h, duration = get_time_slots(staff.store)

        calendar = {}
        for slot in time_slots:
            slot_key = slot['label']
            calendar[slot_key] = {d: True for d in days}

        start_time = datetime.datetime.combine(start_day, datetime.time(hour=open_h, minute=0, second=0))
        end_time = datetime.datetime.combine(end_day, datetime.time(hour=close_h, minute=0, second=0))

        for schedule in (
            Schedule.objects.filter(staff=staff, is_cancelled=False)
            .exclude(Q(start__gt=end_time) | Q(end__lt=start_time))
        ):
            local_dt = timezone.localtime(schedule.start)
            booking_date = local_dt.date()
            booking_label = f"{local_dt.hour}:{local_dt.minute:02d}"
            if booking_label in calendar and booking_date in calendar[booking_label]:
                calendar[booking_label][booking_date] = 'Temp' if schedule.is_temporary else 'Booked'

        context['staff'] = staff
        context['calendar'] = calendar
        context['days'] = days
        context['start_day'] = start_day
        context['end_day'] = end_day
        context['before'] = days[0] - datetime.timedelta(days=7)
        context['next'] = days[-1] + datetime.timedelta(days=1)
        context['today'] = today
        context['public_holidays'] = settings.PUBLIC_HOLIDAYS
        context['time_slots'] = time_slots
        context['slot_duration'] = duration
        return context


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = []


class PreBooking(generic.CreateView):
    model = Schedule
    form_class = ScheduleForm
    template_name = 'booking/booking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff'] = get_object_or_404(Staff, pk=self.kwargs['pk'])
        return context

    def form_valid(self, form):
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])
        price = staff.price

        year = int(self.kwargs.get('year'))
        month = int(self.kwargs.get('month'))
        day = int(self.kwargs.get('day'))
        hour = int(self.kwargs.get('hour'))
        minute = int(self.kwargs.get('minute', 0))

        tz = pytz.timezone(settings.TIME_ZONE)
        start = datetime.datetime(year=year, month=month, day=day, hour=hour, minute=minute)

        # 動的コマ長
        _, _, _, duration = get_time_slots(staff.store)
        end = start + datetime.timedelta(minutes=duration)

        if Schedule.objects.filter(staff=staff, start=start, is_cancelled=False).exists():
            messages.error(self.request, 'すみません、入れ違いで予約がありました。別の日時はどうですか。')
            return HttpResponseRedirect(reverse('booking:staff_calendar', args=[staff.id]))

        schedule = form.save(commit=False)
        schedule.staff = staff
        schedule.start = start
        schedule.end = end
        schedule.is_temporary = True
        schedule.price = price
        schedule.temporary_booked_at = datetime.datetime.now(tz)

        self.request.session['temporary_booking'] = {
            'reservation_number': str(schedule.reservation_number),
            'start': start.isoformat(),
            'end': end.isoformat(),
            'price': price,
            'is_temporary': schedule.is_temporary,
            'staff_id': staff.id,
            'staff_name': staff.name,
        }

        return redirect('booking:channel_choice')


class BookingChannelChoice(generic.TemplateView):
    """LINE or メール選択画面"""
    template_name = 'booking/channel_choice.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['booking'] = self.request.session.get('temporary_booking')
        return context


class EmailBookingForm(forms.Form):
    customer_name = forms.CharField(max_length=255, label='お名前')
    customer_email = forms.EmailField(label='メールアドレス')


class EmailBookingView(View):
    """メアド+名前入力 → OTP送信"""

    def get(self, request):
        form = EmailBookingForm()
        booking = request.session.get('temporary_booking')
        if not booking:
            return redirect('booking:booking_top')
        return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

    def post(self, request):
        form = EmailBookingForm(request.POST)
        booking = request.session.get('temporary_booking')
        if not booking:
            return redirect('booking:booking_top')

        if not form.is_valid():
            return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

        customer_name = form.cleaned_data['customer_name']
        customer_email = form.cleaned_data['customer_email']

        # 6桁OTP生成
        otp = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        otp_expires = timezone.now() + datetime.timedelta(minutes=10)

        # セッションに保存
        request.session['email_booking'] = {
            'customer_name': customer_name,
            'customer_email': customer_email,
            'otp_hash': otp_hash,
            'otp_expires': otp_expires.isoformat(),
        }

        # OTPメール送信
        try:
            send_mail(
                subject='予約認証コード',
                message=f'{customer_name}様\n\nご予約の認証コードは {otp} です。\n10分以内にご入力ください。',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[customer_email],
                fail_silently=False,
            )
        except Exception as e:
            logger.error('OTPメール送信失敗: %s', e)
            messages.error(request, 'メール送信に失敗しました。もう一度お試しください。')
            return render(request, 'booking/email_form.html', {'form': form, 'booking': booking})

        return redirect('booking:email_verify')


class EmailVerifyView(View):
    """OTP入力 → 認証 → 仮予約作成 → 決済URL送信"""

    def get(self, request):
        email_booking = request.session.get('email_booking')
        if not email_booking:
            return redirect('booking:booking_top')
        return render(request, 'booking/email_verify.html', {'email': email_booking['customer_email']})

    def post(self, request):
        email_booking = request.session.get('email_booking')
        temporary_booking = request.session.get('temporary_booking')

        if not email_booking or not temporary_booking:
            return redirect('booking:booking_top')

        otp_input = request.POST.get('otp', '').strip()
        otp_hash_input = hashlib.sha256(otp_input.encode('utf-8')).hexdigest()

        # ハッシュ照合
        if otp_hash_input != email_booking['otp_hash']:
            messages.error(request, '認証コードが正しくありません。')
            return render(request, 'booking/email_verify.html', {'email': email_booking['customer_email']})

        # 有効期限チェック
        from datetime import datetime as dt
        otp_expires = dt.fromisoformat(email_booking['otp_expires'])
        if timezone.is_naive(otp_expires):
            otp_expires = timezone.make_aware(otp_expires)
        if timezone.now() > otp_expires:
            messages.error(request, '認証コードの有効期限が切れています。もう一度やり直してください。')
            return redirect('booking:email_booking')

        # 仮予約作成
        tz = pytz.timezone(settings.TIME_ZONE)
        schedule = Schedule(
            reservation_number=temporary_booking['reservation_number'],
            start=timezone.make_aware(dt.fromisoformat(temporary_booking['start'])),
            end=timezone.make_aware(dt.fromisoformat(temporary_booking['end'])),
            price=temporary_booking['price'],
            customer_name=email_booking['customer_name'],
            staff_id=temporary_booking['staff_id'],
            is_temporary=True,
            temporary_booked_at=timezone.now(),
            booking_channel='email',
            customer_email=email_booking['customer_email'],
            email_verified=True,
        )
        schedule.save()

        # Coiney決済URL取得
        from datetime import timedelta as td
        now = dt.now()
        expired_on = now + td(days=1)
        expired_on_str = expired_on.strftime('%Y-%m-%d')

        payment_api_url = settings.PAYMENT_API_URL
        headers = {
            'Authorization': 'Bearer ' + settings.PAYMENT_API_KEY,
            'Content-Type': 'application/json',
        }
        reservation_number = schedule.reservation_number
        webhook_url = f"{settings.WEBHOOK_URL_BASE}{reservation_number}/"

        data = {
            "amount": schedule.price,
            "currency": "jpy",
            "locale": "ja_JP",
            "cancelUrl": settings.CANCEL_URL,
            "webhookUrl": webhook_url,
            "method": "creditcard",
            "subject": "ご予約料金",
            "description": "ウェブサイトからの支払い",
            "remarks": "仮予約から15分を過ぎますと自動的にキャンセルとなります。あらかじめご了承ください。",
            "metadata": {"orderId": str(reservation_number)},
            "expiredOn": expired_on_str,
        }

        payment_url = None
        try:
            response = requests.post(payment_api_url, headers=headers, data=json.dumps(data))
            if response.status_code == 201:
                payment_url = response.json()['links']['paymentUrl']
        except Exception as e:
            logger.error('決済URL取得失敗: %s', e)

        if payment_url:
            schedule.payment_url = payment_url
            schedule.save(update_fields=['payment_url'])

            # メールで決済URL送信
            try:
                send_mail(
                    subject='予約決済のご案内',
                    message=(
                        f'{email_booking["customer_name"]}様\n\n'
                        f'以下のURLから決済を行ってください。\n'
                        f'{payment_url}\n\n'
                        f'15分以内にお支払いがない場合、仮予約は自動キャンセルされます。\n'
                        f'あらかじめご了承ください。'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email_booking['customer_email']],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error('決済URLメール送信失敗: %s', e)

        # セッションクリア
        del request.session['temporary_booking']
        del request.session['email_booking']

        return render(request, 'booking/email_payment_sent.html', {
            'customer_email': email_booking['customer_email'],
            'customer_name': email_booking['customer_name'],
            'payment_url_sent': bool(payment_url),
        })


class CancelReservationView(LoginRequiredMixin, View):
    def post(self, request, schedule_id):
        schedule = get_object_or_404(Schedule, id=schedule_id)
        # 本人またはスタッフ/管理者のみキャンセル可能
        is_owner = (schedule.line_user_hash and
                    schedule.line_user_hash == Schedule.make_line_user_hash(
                        request.session.get('line_user_id', '')))
        is_staff_or_admin = (request.user.is_staff or request.user.is_superuser)
        if not is_owner and not is_staff_or_admin:
            raise PermissionDenied
        schedule.is_cancelled = True
        schedule.save(update_fields=["is_cancelled"])

        # スタッフ通知（任意）
        try:
            staff_line_account_id = schedule.staff.line_id
            if staff_line_account_id:
                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
                local_tz = pytz.timezone('Asia/Tokyo')
                local_time = timezone.localtime(schedule.start, local_tz)
                line_bot_api.push_message(
                    staff_line_account_id,
                    TextSendMessage(text=f'予約がキャンセルされました。予約日時: {local_time}')
                )
        except Exception as e:
            logger.warning('CancelReservationView: スタッフLINE通知に失敗しました: %s', e)

        # 顧客通知（復号できる場合のみ）
        try:
            customer_user_id = schedule.get_line_user_id()
            if customer_user_id:
                line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)
                local_tz = pytz.timezone('Asia/Tokyo')
                local_time = timezone.localtime(schedule.start, local_tz)
                line_bot_api.push_message(
                    customer_user_id,
                    TextSendMessage(text=f'あなたの予約がキャンセルされました。予約日時: {local_time}')
                )
        except Exception as e:
            logger.warning('CancelReservationView: 顧客LINE通知に失敗しました: %s', e)

        return render(request, 'booking/cancel_success.html', {"schedule": schedule})


class MyPage(LoginRequiredMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['staff_list'] = Staff.objects.filter(user=self.request.user).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(
            staff__user=self.request.user,
            start__gte=timezone.now()
        ).order_by('start')
        return context


class MyPageWithPk(OnlyUserMixin, generic.TemplateView):
    template_name = 'booking/my_page.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = get_object_or_404(User, pk=self.kwargs['pk'])
        context['staff_list'] = Staff.objects.filter(user__pk=self.kwargs['pk']).order_by('name')
        context['schedule_list'] = Schedule.objects.filter(
            staff__user__pk=self.kwargs['pk'],
            start__gte=timezone.now()
        ).order_by('start')
        return context


class MyPageCalendar(OnlyStaffMixin, StaffCalendar):
    template_name = 'booking/my_page_calendar.html'


class MyPageDayDetail(OnlyStaffMixin, generic.TemplateView):
    template_name = 'booking/my_page_day_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, pk=self.kwargs['pk'])

        year = self.kwargs.get('year')
        month = self.kwargs.get('month')
        day = self.kwargs.get('day')
        date = datetime.date(year=year, month=month, day=day)

        # 動的タイムスロット
        time_slots, open_h, close_h, duration = get_time_slots(staff.store)

        calendar = {}
        for slot in time_slots:
            calendar[slot['label']] = []

        start_time = datetime.datetime.combine(date, datetime.time(hour=open_h, minute=0, second=0))
        end_time = datetime.datetime.combine(date, datetime.time(hour=close_h, minute=0, second=0))

        for schedule in Schedule.objects.filter(staff=staff).exclude(
            Q(start__gt=end_time) | Q(end__lt=start_time)
        ):
            local_dt = timezone.localtime(schedule.start)
            booking_label = f"{local_dt.hour}:{local_dt.minute:02d}"
            if booking_label in calendar:
                calendar[booking_label].append(schedule)

        has_any_schedule = any(schedules for schedules in calendar.values())
        context['calendar'] = calendar
        context['staff'] = staff
        context['has_any_schedule'] = has_any_schedule
        context['time_slots'] = time_slots
        return context


class MyPageSchedule(OnlyScheduleMixin, generic.UpdateView):
    model = Schedule
    fields = ('start', 'end', 'customer_name', 'memo', 'price', 'is_temporary', 'is_cancelled')
    success_url = reverse_lazy('booking:my_page')


class MyPageScheduleDelete(OnlyScheduleMixin, generic.DeleteView):
    model = Schedule
    success_url = reverse_lazy('booking:my_page')


@login_required
@require_POST
def my_page_holiday_add(request, pk, year, month, day, hour):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        start = datetime.datetime(year=year, month=month, day=day, hour=hour)
        end = datetime.datetime(year=year, month=month, day=day, hour=hour + 1)
        Schedule.objects.create(staff=staff, start=start, end=end, is_temporary=False, price=0)
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
@require_POST
def my_page_day_add(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        for num in range(9):
            start = datetime.datetime(year=year, month=month, day=day, hour=9 + num)
            end = datetime.datetime(year=year, month=month, day=day, hour=10 + num)
            Schedule.objects.create(staff=staff, start=start, end=end, is_temporary=False, price=0)
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
@require_POST
def my_page_day_delete(request, pk, year, month, day):
    staff = get_object_or_404(Staff, pk=pk)
    if staff.user == request.user or request.user.is_superuser:
        start = datetime.datetime(year=year, month=month, day=day, hour=9)
        end = datetime.datetime(year=year, month=month, day=day, hour=17)
        # 顧客予約を保護: customer_nameが空のスタッフ作成ブロックのみ削除
        Schedule.objects.filter(
            staff=staff, start__gte=start, end__lte=end,
            customer_name__isnull=True, price=0
        ).delete()
        return redirect('booking:my_page_day_detail', pk=pk, year=year, month=month, day=day)
    raise PermissionDenied


@login_required
def upload_file(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if request.method == 'POST':
        form = StaffForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect('/success/url/')
    else:
        form = StaffForm()
    return render(request, 'upload.html', {'form': form})


def process_payment(payment_response, request, orderId):
    if payment_response.get('type') == 'payment.succeeded':
        schedule = Schedule.objects.get(reservation_number=orderId)
        schedule.is_temporary = False
        schedule.save(update_fields=["is_temporary"])

        line_bot_api = LineBotApi(settings.LINE_ACCESS_TOKEN)

        # スタッフ通知
        staff_line_account_id = schedule.staff.line_id
        if staff_line_account_id:
            local_tz = pytz.timezone('Asia/Tokyo')
            local_time = schedule.start.astimezone(local_tz)
            message_text = '予約が完了しました。予約者: {}, 日時: {}'.format(
                schedule.customer_name or 'Unknown',
                local_time
            )
            try:
                line_bot_api.push_message(staff_line_account_id, TextSendMessage(text=message_text))
            except LineBotApiError as e:
                print('スタッフメッセージにてLineBotApiErrorが発生しました:', e)

        # ▼顧客通知：Scheduleに保存した暗号化LINE user id を復号してpush
        user_id = None
        try:
            user_id = schedule.get_line_user_id()
        except Exception as e:
            logger.warning('Failed to decrypt LINE user id: %s', e)

        if user_id:
            timer_url = reverse('booking:LINETimerView', args=[user_id])
            encoded_timer_url = quote(timer_url)
            message_text = (
                '決済が完了しました。こちらのURLから予約情報・タイマーを確認できます: '
                + '<' + 'https://timebaibai.com/' + encoded_timer_url + '>'
            )
            try:
                line_bot_api.push_message(user_id, TextSendMessage(text=message_text))
            except LineBotApiError as e:
                print('顧客向け決済完了メッセージにてLineBotApiErrorが発生しました:', e)

        # メール予約の場合: 決済完了メールを送信
        if schedule.booking_channel == 'email' and schedule.customer_email:
            local_tz = pytz.timezone('Asia/Tokyo')
            local_time = schedule.start.astimezone(local_tz)
            try:
                send_mail(
                    subject='予約確定のお知らせ',
                    message=(
                        f'{schedule.customer_name}様\n\n'
                        f'予約が確定しました。\n\n'
                        f'占い師: {schedule.staff.name}\n'
                        f'日時: {local_time.strftime("%Y年%m月%d日 %H:%M")}\n'
                        f'料金: {schedule.price}円\n\n'
                        f'ご予約ありがとうございます。'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[schedule.customer_email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning('メール予約確定通知の送信に失敗: %s', e)

    return JsonResponse({"status": "success"})


@csrf_exempt
def coiney_webhook(request, orderId):
    if request.method != 'POST':
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Webhook署名検証
    webhook_secret = getattr(settings, 'COINEY_WEBHOOK_SECRET', None)
    if webhook_secret:
        import hmac as _hmac
        signature = request.headers.get('X-Coiney-Signature', '')
        expected = _hmac.new(
            webhook_secret.encode(), request.body, hashlib.sha256
        ).hexdigest()
        if not _hmac.compare_digest(signature, expected):
            logger.warning('coiney_webhook: 署名検証に失敗しました orderId=%s', orderId)
            return JsonResponse({"error": "Invalid signature"}, status=403)
    else:
        logger.warning('coiney_webhook: COINEY_WEBHOOK_SECRET が未設定です。署名検証をスキップしています。')

    # リクエストヘッダーのログ出力（機密情報を除外）
    safe_meta = {k: v for k, v in request.META.items()
                 if k.startswith('HTTP_') and k not in ('HTTP_COOKIE', 'HTTP_AUTHORIZATION')}
    logger.info('coiney_webhook called: orderId=%s, headers=%s', orderId, safe_meta)

    if orderId:
        view = PayingSuccessView()
        view._called_from_webhook = True
        return view.post(request, orderId)
    return JsonResponse({"error": "orderId not found in request body"}, status=400)


def your_view(request):
    medias = Media.objects.order_by('-created_at')
    return render(request, 'booking/base.html', {'medias': medias})


# ==========================================================
# 追加機能: 在庫 / 注文 / 入庫QR / 多言語（商品翻訳）
# ==========================================================

def _resolve_lang(request, store: Store) -> str:
    """言語決定: ?lang=xx があれば優先、なければ店舗既定、最後に ja"""
    lang = request.GET.get("lang")
    if lang:
        return lang
    store_lang = getattr(store, "default_language", None)
    return store_lang or "ja"


def _product_display(product: Product, lang: str) -> dict:
    tr = product.translations.filter(lang=lang).first()
    return {
        "id": product.id,
        "sku": product.sku,
        "name": tr.name if tr else product.name,
        "description": tr.description if tr else product.description,
        "price": product.price,
        "stock": product.stock,
        "is_sold_out": (product.stock <= 0),
        "category_id": product.category_id,
    }


class CustomerMenuView(generic.TemplateView):
    """客側メニュー（テンプレ）
    URL: /booking/menu/<store_id>/
    Template: booking/customer_menu.html
    """
    template_name = "booking/customer_menu.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = get_object_or_404(Store, pk=self.kwargs["store_id"])
        lang = _resolve_lang(self.request, store)

        categories = Category.objects.filter(store=store).order_by("sort_order", "name")
        products = Product.objects.filter(store=store, is_active=True).select_related("category")

        ctx.update({
            "store": store,
            "lang": lang,
            "categories": categories,
            "products": [_product_display(p, lang) for p in products],
        })
        return ctx


class CustomerMenuJsonAPIView(APIView):
    """客側メニュー（JSON）
    GET /booking/api/menu?store_id=1&lang=en
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        store_id = request.GET.get("store_id")
        if not store_id:
            return Response({"detail": "store_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)
        lang = _resolve_lang(request, store)

        categories = Category.objects.filter(store=store).order_by("sort_order", "name")
        products = Product.objects.filter(store=store, is_active=True).select_related("category")

        return Response({
            "store": {"id": store.id, "name": store.name},
            "lang": lang,
            "categories": [{"id": c.id, "name": c.name} for c in categories],
            "products": [_product_display(p, lang) for p in products],
        })


class ProductAlternativesAPIView(APIView):
    """売切時の代替候補 API
    GET /booking/api/products/alternatives/?product_id=123&lang=ja
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        product_id = request.GET.get("product_id")
        if not product_id:
            return Response({"detail": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, pk=product_id)
        store = product.store
        lang = _resolve_lang(request, store)

        qs = Product.objects.filter(store=store, is_active=True, stock__gt=0)
        if product.category_id:
            qs = qs.filter(category_id=product.category_id)

        # シンプル: 人気順 -> 価格順
        qs = qs.exclude(id=product.id).order_by("-popularity", "price")[:5]
        return Response({"alternatives": [_product_display(p, lang) for p in qs]})

class OrderCreateAPIView(APIView):
    """注文作成（在庫引当=OUT + StockMovement 作成）
    POST /booking/api/orders/create/
    {
      "store_id": 1,
      "schedule_id": 10,   # 任意
      "items": [{"product_id": 123, "qty": 2}, ...]
    }

    同時更新（多重注文/多重入庫）に耐えるため、対象商品の行をまとめて `select_for_update()` でロックし、
    在庫チェック→出庫→明細作成を同一トランザクションで行う。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        # セッションベースの簡易保護: store_idの妥当性チェックで不正大量注文を抑止
        store_id = request.data.get("store_id")
        items = request.data.get("items", [])
        if not items or len(items) > 50:
            return Response({"detail": "items must be 1-50"}, status=status.HTTP_400_BAD_REQUEST)
        schedule_id = request.data.get("schedule_id")

        if not store_id or not isinstance(items, list) or not items:
            return Response({"detail": "store_id and items are required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)
        schedule = get_object_or_404(Schedule, pk=schedule_id) if schedule_id else None
        customer_hash = schedule.line_user_hash if (schedule and schedule.line_user_hash) else None

        # items を正規化（product_id 単位で合算）
        normalized = {}
        for it in items:
            pid = it.get("product_id")
            try:
                qty = int(it.get("qty", 1))
            except Exception:
                qty = 0
            if not pid or qty <= 0:
                continue
            normalized[pid] = normalized.get(pid, 0) + qty

        if not normalized:
            return Response({"detail": "items are invalid"}, status=status.HTTP_400_BAD_REQUEST)

        product_ids = sorted(normalized.keys())

        with transaction.atomic():
            order = Order.objects.create(
                store=store,
                schedule=schedule,
                customer_line_user_hash=customer_hash,
                status=Order.STATUS_OPEN,
            )

            # 対象商品をまとめてロック（デッドロック回避のためID順）
            locked_products = list(
                Product.objects.select_for_update()
                .filter(store=store, is_active=True, id__in=product_ids)
                .order_by("id")
            )
            product_map = {p.id: p for p in locked_products}

            missing = [pid for pid in product_ids if pid not in product_map]
            if missing:
                return Response({"detail": f"product not found: {missing}"}, status=status.HTTP_404_NOT_FOUND)

            # 在庫チェック（ロック済み）
            for pid in product_ids:
                p = product_map[pid]
                qty = normalized[pid]
                if int(p.stock) - int(qty) < 0:
                    return Response({"detail": f"insufficient stock: {p.sku}"}, status=status.HTTP_409_CONFLICT)

            # 出庫 + 明細作成
            for pid in product_ids:
                p = product_map[pid]
                qty = normalized[pid]

                StockMovement.objects.create(
                    store=store,
                    product=p,
                    movement_type=StockMovement.TYPE_OUT,
                    qty=qty,
                    by_staff=None,
                    note=f"order#{order.id}",
                )

                # ロック済みのインスタンスに対して更新
                apply_stock_movement(p, StockMovement.TYPE_OUT, qty)

                OrderItem.objects.create(
                    order=order,
                    product=p,
                    qty=qty,
                    unit_price=p.price,
                    status=OrderItem.STATUS_ORDERED,
                )

        return Response({"order_id": order.id}, status=status.HTTP_201_CREATED)

class OrderStatusAPIView(APIView):
    """注文状況（客側ポーリング用）
    GET /booking/api/orders/status/?order_id=1
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        order_id = request.GET.get("order_id")
        if not order_id:
            return Response({"detail": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, pk=order_id)

        items = []
        for it in order.items.select_related("product").order_by("created_at"):
            items.append({
                "id": it.id,
                "product_id": it.product_id,
                "product_sku": it.product.sku,
                "product_name": it.product.name,
                "qty": it.qty,
                "unit_price": it.unit_price,
                "status": it.status,
                "updated_at": it.updated_at.isoformat(),
            })

        return Response({
            "order_id": order.id,
            "status": order.status,
            "items": items,
            "updated_at": order.updated_at.isoformat(),
        })


class StaffMarkServedAPIView(LoginRequiredMixin, APIView):
    """スタッフ側: 提供完了"""

    def post(self, request, *args, **kwargs):
        item_id = request.data.get("order_item_id")
        if not item_id:
            return Response({"detail": "order_item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(OrderItem, pk=item_id)

        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except Exception:
                raise PermissionDenied
            if staff.store_id != item.order.store_id:
                raise PermissionDenied

        item.status = OrderItem.STATUS_SERVED
        item.save(update_fields=["status", "updated_at"])

        return Response({"ok": True, "order_item_id": item.id, "status": item.status})


class InboundQRView(LoginRequiredMixin, generic.TemplateView):
    """入庫QR画面（スタッフ用）
    GET /booking/stock/inbound/?store_id=1&sku=ABC
    Template: booking/inbound_qr.html
    """
    template_name = "booking/inbound_qr.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sku = self.request.GET.get("sku", "")
        store_id = self.request.GET.get("store_id")

        if store_id:
            store = get_object_or_404(Store, pk=store_id)
        else:
            try:
                store = self.request.user.staff.store
            except Exception:
                store = None

        product = None
        if store and sku:
            product = Product.objects.filter(store=store, sku=sku).first()

        ctx.update({
            "store": store,
            "sku": sku,
            "product": product,
        })
        return ctx

class InboundApplyAPIView(LoginRequiredMixin, APIView):
    """入庫登録 API
    POST /booking/api/stock/inbound/apply/
    {"store_id": 1, "sku": "ABC", "qty": 10, "note": "仕入れ"}

    同時更新（複数スタッフが同時に入庫登録など）に耐えるため、対象商品の行を `select_for_update()` でロック。
    """

    def post(self, request, *args, **kwargs):
        sku = request.data.get("sku")
        store_id = request.data.get("store_id")
        try:
            qty = int(request.data.get("qty", 0))
        except Exception:
            qty = 0
        note = request.data.get("note", "")

        if not sku or not store_id or qty <= 0:
            return Response({"detail": "sku, store_id, qty(>0) are required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)

        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except Exception:
                raise PermissionDenied
            if staff.store_id != store.id:
                raise PermissionDenied
        else:
            staff = None

        with transaction.atomic():
            # ★同時更新対策：商品行をロック
            try:
                product = Product.objects.select_for_update().get(store=store, sku=sku)
            except Product.DoesNotExist:
                return Response({"detail": "product not found"}, status=status.HTTP_404_NOT_FOUND)

            StockMovement.objects.create(
                store=store,
                product=product,
                movement_type=StockMovement.TYPE_IN,
                qty=qty,
                by_staff=staff,
                note=note,
            )

            apply_stock_movement(product, StockMovement.TYPE_IN, qty)

            # apply_stock_movement が save() するので、ここでは refresh だけして返す
            product.refresh_from_db(fields=["stock"])

        return Response({"ok": True, "sku": sku, "stock": product.stock})
    
class OrderItemStatusUpdateAPIView(LoginRequiredMixin, APIView):
    """
    スタッフ側: 注文アイテムのステータス更新
    POST /booking/api/staff/orders/items/<item_id>/status/
    body: {"status": "PREPARING"} or {"status": "SERVED"}

    遷移:
      ORDERED -> PREPARING -> SERVED
    """

    def post(self, request, item_id, *args, **kwargs):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"detail": "status is required"}, status=status.HTTP_400_BAD_REQUEST)

        preparing = getattr(OrderItem, "STATUS_PREPARING", "PREPARING")

        allowed = {OrderItem.STATUS_ORDERED, preparing, OrderItem.STATUS_SERVED}
        if new_status not in allowed:
            return Response({"detail": "invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(OrderItem, pk=item_id)

        # 権限: 自店舗のみ（superuserは全許可）
        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except Exception:
                raise PermissionDenied
            if staff.store_id != item.order.store_id:
                raise PermissionDenied

        current = item.status

        if current == OrderItem.STATUS_SERVED:
            return Response({"detail": "already served"}, status=status.HTTP_409_CONFLICT)

        # 飛び級禁止
        if current == OrderItem.STATUS_ORDERED and new_status != preparing:
            return Response({"detail": "must transition ORDERED -> PREPARING"}, status=status.HTTP_409_CONFLICT)

        if current == preparing and new_status != OrderItem.STATUS_SERVED:
            return Response({"detail": "must transition PREPARING -> SERVED"}, status=status.HTTP_409_CONFLICT)

        item.status = new_status
        item.save(update_fields=["status", "updated_at"])

        return Response({"ok": True, "order_item_id": item.id, "status": item.status})


# ===== Phase 3: Sensor Dashboard View (HTML page, APIs in views_dashboard.py) =====

class IoTSensorDashboardView(generic.TemplateView):
    template_name = 'booking/iot_sensor_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['devices'] = IoTDevice.objects.filter(is_active=True).select_related('store')
        return ctx


# ===== Round2: シフト管理ビュー =====

class StaffShiftCalendarView(LoginRequiredMixin, generic.TemplateView):
    """占い師が自分のシフトカレンダーを表示"""
    template_name = 'booking/staff_shift_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, user=self.request.user)
        today = datetime.date.today()

        # 現在募集中のシフト期間を取得
        open_periods = ShiftPeriod.objects.filter(
            store=staff.store,
            status='open',
        ).order_by('year_month')

        # 自分のシフト希望
        my_requests = ShiftRequest.objects.filter(
            staff=staff,
        ).select_related('period').order_by('date', 'start_hour')

        context['staff'] = staff
        context['today'] = today
        context['open_periods'] = open_periods
        context['my_requests'] = my_requests
        return context


class StaffShiftSubmitView(LoginRequiredMixin, View):
    """占い師がシフト希望を登録/変更"""

    def get(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)
        open_h, close_h = get_hour_range(staff.store)

        existing = ShiftRequest.objects.filter(
            period=period, staff=staff,
        ).order_by('date', 'start_hour')

        return render(request, 'booking/staff_shift_submit.html', {
            'staff': staff,
            'period': period,
            'existing': existing,
            'open_hour': open_h,
            'close_hour': close_h,
        })

    def post(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)

        if period.status != 'open':
            messages.error(request, 'この募集期間は締め切られています。')
            return redirect('booking:staff_shift_calendar')

        open_h, close_h = get_hour_range(staff.store)

        date_str = request.POST.get('date')
        start_hour = request.POST.get('start_hour')
        end_hour = request.POST.get('end_hour')
        preference = request.POST.get('preference', 'available')
        note = request.POST.get('note', '')

        if not all([date_str, start_hour, end_hour]):
            messages.error(request, '日付と時間を入力してください。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        try:
            date = datetime.date.fromisoformat(date_str)
            start_h = int(start_hour)
            end_h = int(end_hour)
        except (ValueError, TypeError):
            messages.error(request, '入力値が不正です。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        # 営業時間バリデーション
        if start_h < open_h or end_h > close_h or start_h >= end_h:
            messages.error(request, f'営業時間({open_h}:00-{close_h}:00)の範囲で入力してください。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        ShiftRequest.objects.update_or_create(
            period=period,
            staff=staff,
            date=date,
            start_hour=start_h,
            defaults={
                'end_hour': end_h,
                'preference': preference,
                'note': note,
            },
        )

        messages.success(request, 'シフト希望を登録しました。')
        return redirect('booking:staff_shift_submit', period_id=period_id)


# ===== Round2: 静的ページ =====

class PrivacyPolicyView(generic.TemplateView):
    template_name = 'booking/privacy_policy.html'


class TokushohoView(generic.TemplateView):
    template_name = 'booking/tokushoho.html'


# ===== Phase 5: Property Views (re-exports for URL routing) =====

from booking.views_property import PropertyListView, PropertyDetailView  # noqa: E402, F401