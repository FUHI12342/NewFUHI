"""IoT API views: IoTEventAPIView, IoTConfigAPIView, IRSendAPIView,
IoTMQ9GraphView, IoTSensorDashboardView, and helper functions."""
import json
import logging
import time
from typing import Optional, Dict, Any, Tuple

from django.conf import settings
from django.utils import timezone
from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

from linebot import LineBotApi

from booking.admin_site import custom_site
from booking.models import IoTDevice, IoTEvent, IRCode

logger = logging.getLogger(__name__)


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
        if "sensors" in incoming and isinstance(incoming["sensors"], dict):
            return incoming, incoming["sensors"]
        return incoming, incoming

    parsed = _safe_json_loads(str(incoming))
    if isinstance(parsed, dict):
        if "sensors" in parsed and isinstance(parsed["sensors"], dict):
            return parsed, parsed["sensors"]
        return parsed, parsed

    return None, {}


def _pick_value(request_data: Dict[str, Any], sensors_dict: Dict[str, Any],
                payload_raw_dict: Optional[dict], key: str) -> Any:
    """
    Pick sensor value from multiple sources with proper None handling.

    Priority: 1) request_data, 2) sensors_dict, 3) payload_raw_dict
    Uses 'is not None' to properly handle 0.0 values.
    """
    if key in request_data:
        value = request_data.get(key)
        if value is not None:
            return value

    if key in sensors_dict:
        value = sensors_dict.get(key)
        if value is not None:
            return value

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
            return float(value)
        else:
            return None
    except (ValueError, TypeError):
        return None


# --------------------------------------------------
# LINE Push通知ヘルパー（指数バックオフリトライ付き）
# --------------------------------------------------
def _send_line_push_with_retry(user_id: str, message: str, device_id: str = '', max_retries: int = 3):
    """LineBotApi.push_message をリトライ付きで送信"""
    from linebot.models import TextSendMessage
    for attempt in range(max_retries):
        try:
            bot = LineBotApi(settings.LINE_ACCESS_TOKEN)
            bot.push_message(user_id, TextSendMessage(text=message))
            return True
        except Exception as e:
            logger.warning("LINE push attempt %d/%d failed (device=%s): %s", attempt + 1, max_retries, device_id, e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return False


# --------------------------------------------------
# IoTデバイスAPIレートリミット
# --------------------------------------------------
class IoTDeviceThrottle(SimpleRateThrottle):
    """IoTデバイス単位のレートリミット（10リクエスト/分）"""
    rate = '10/min'

    def get_cache_key(self, request, view):
        device_name = request.data.get('device', '')
        return f'iot_throttle_{device_name}'


class IoTEventAPIView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [IoTDeviceThrottle]

    def post(self, request, *args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            return Response({"detail": "X-API-KEY header is required"}, status=status.HTTP_400_BAD_REQUEST)

        device_name = request.data.get("device")
        if not device_name:
            return Response({"detail": "device is required"}, status=status.HTTP_400_BAD_REQUEST)

        api_key_hash = IoTDevice.hash_api_key(api_key)
        try:
            device = IoTDevice.objects.get(api_key_hash=api_key_hash, external_id=device_name)
        except IoTDevice.DoesNotExist:
            return Response({"detail": "device not found"}, status=status.HTTP_404_NOT_FOUND)

        event_type = request.data.get("event_type", "sensor")
        incoming_payload = request.data.get("payload", None)

        payload_raw_dict, sensors_dict = _normalize_payload(incoming_payload)

        sensor_keys = ["mq9", "light", "sound", "temp", "hum", "ts"]
        payload_dict = {}

        for key in sensor_keys:
            value = _pick_value(request.data, sensors_dict, payload_raw_dict, key)
            payload_dict[key] = value

        if payload_dict["mq9"] is None:
            mq9_alt = request.data.get("mq9_value")
            if mq9_alt is not None:
                payload_dict["mq9"] = mq9_alt

        mq9_value = _to_float_or_none(payload_dict["mq9"])
        light_value = _to_float_or_none(payload_dict.get("light"))
        sound_value = _to_float_or_none(payload_dict.get("sound"))

        pir_raw = _pick_value(request.data, sensors_dict, payload_raw_dict, "pir")
        pir_triggered = None
        if pir_raw is not None:
            pir_triggered = bool(pir_raw)

        evt = IoTEvent.objects.create(
            device=device,
            event_type=event_type,
            payload=json.dumps(payload_dict, ensure_ascii=False),
            mq9_value=mq9_value,
            light_value=light_value,
            sound_value=sound_value,
            pir_triggered=pir_triggered,
        )

        device.last_seen_at = timezone.now()
        device.save(update_fields=["last_seen_at"])

        if mq9_value is not None:
            from .ventilation_control import check_ventilation_rules
            try:
                check_ventilation_rules(device, mq9_value)
            except Exception as vent_err:
                logger.warning(f"Ventilation check failed: {vent_err}")

        if event_type == "mq9_alarm" and device.alert_enabled and device.alert_line_user_id:
            mq9_val = mq9_value or 'N/A'
            threshold = device.mq9_threshold or 500
            alert_message = (
                f'\u26a0\ufe0f ガス検知アラート\n'
                f'デバイス: {device.name}\n'
                f'MQ-9値: {mq9_val} (閾値: {threshold})\n'
                f'店舗: {device.store.name}'
            )
            _send_line_push_with_retry(device.alert_line_user_id, alert_message, device.external_id)

        if event_type == "ir_learned":
            try:
                payload_data = json.loads(evt.payload) if evt.payload else {}
                protocol = str(payload_data.get('protocol', 'UNKNOWN'))
                raw_pulses = payload_data.get('raw', payload_data.get('raw_sample', []))
                IRCode.objects.create(
                    device=device,
                    name=f'学習コード {timezone.now():%Y%m%d_%H%M%S}',
                    protocol=protocol,
                    code=str(payload_data.get('code', '')),
                    address=str(payload_data.get('address', '')),
                    command=str(payload_data.get('command', '')),
                    raw_data=json.dumps(raw_pulses),
                )
            except Exception as ir_err:
                logger.warning(f"IRCode auto-save failed for device {device.external_id}: {ir_err}")

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

        api_key_hash = IoTDevice.hash_api_key(api_key)
        try:
            device = IoTDevice.objects.get(external_id=external_id, api_key_hash=api_key_hash, is_active=True)
        except IoTDevice.DoesNotExist:
            return Response({'detail': '認証失敗'}, status=status.HTTP_403_FORBIDDEN)

        DEFAULT_MQ9_THRESHOLD = 500
        mq9_threshold = device.mq9_threshold if device.mq9_threshold is not None else DEFAULT_MQ9_THRESHOLD

        if mq9_threshold <= 0:
            logger.warning(f"IoT device {device.external_id} has invalid threshold {mq9_threshold}, using default")
            mq9_threshold = DEFAULT_MQ9_THRESHOLD

        wifi_password = device.get_wifi_password() or ''

        response_data = {
            'device': device.external_id,
            'wifi': {'ssid': device.wifi_ssid, 'password': wifi_password},
            'mq9_threshold': int(mq9_threshold),
            'alert_enabled': device.alert_enabled,
        }

        if device.pending_ir_command:
            try:
                response_data['ir_command'] = json.loads(device.pending_ir_command)
            except (json.JSONDecodeError, ValueError):
                pass
            device.pending_ir_command = ''
            device.save(update_fields=['pending_ir_command'])

        return Response(response_data)


class IRSendAPIView(APIView):
    """POST /api/iot/ir/send/ -- queue IR code for device transmission."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        ir_code_id = request.data.get('ir_code_id')
        if not ir_code_id:
            return Response({'detail': 'ir_code_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            ir_code = IRCode.objects.select_related('device').get(pk=ir_code_id)
        except IRCode.DoesNotExist:
            return Response({'detail': 'IRCode not found'}, status=status.HTTP_404_NOT_FOUND)

        device = ir_code.device
        cmd = {
            'action': 'send_ir',
            'protocol': ir_code.protocol,
        }
        if ir_code.protocol == 'RAW' and ir_code.raw_data:
            cmd['raw_data'] = ir_code.raw_data
        else:
            cmd['code'] = ir_code.code
        device.pending_ir_command = json.dumps(cmd)
        device.save(update_fields=['pending_ir_command'])
        return Response({'status': 'queued', 'device': device.external_id, 'ir_code': ir_code.name})


class IoTMQ9GraphView(LoginRequiredMixin, generic.TemplateView):
    template_name = "booking/iot_mq9_graph.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(custom_site.each_context(self.request))
        context["devices"] = list(
            IoTDevice.objects.filter(is_active=True).values("id", "name", "external_id")
        )
        return context


class IoTSensorDashboardView(generic.TemplateView):
    template_name = 'booking/iot_sensor_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['devices'] = IoTDevice.objects.filter(is_active=True).select_related('store')
        return ctx
