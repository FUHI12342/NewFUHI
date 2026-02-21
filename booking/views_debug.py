# booking/views_debug.py
import json
import logging
import os

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import IoTDevice, IoTEvent, SystemConfig

logger = logging.getLogger(__name__)


class AdminDebugPanelView(TemplateView):
    """Admin debug panel — superuser/developer only."""
    template_name = 'admin/booking/debug_panel.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()

        # IoT device connection status
        devices = IoTDevice.objects.filter(is_active=True).select_related('store')
        device_list = []
        for d in devices:
            online = False
            if d.last_seen_at:
                online = (now - d.last_seen_at).total_seconds() < 120
            device_list.append({
                'id': d.id,
                'name': d.name,
                'store': d.store.name,
                'external_id': d.external_id,
                'device_type': d.get_device_type_display(),
                'online': online,
                'last_seen_at': d.last_seen_at,
            })
        ctx['devices'] = device_list

        # Recent API requests (IoTEvent last 50)
        ctx['recent_events'] = IoTEvent.objects.select_related('device').order_by('-created_at')[:50]

        # Current log level
        ctx['current_log_level'] = SystemConfig.get('log_level', settings.LOG_LEVEL)
        ctx['log_levels'] = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

        # Error log tail (last 50 lines)
        log_file = getattr(settings, 'LOG_FILE', '')
        log_lines = []
        if log_file and os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    all_lines = f.readlines()
                    log_lines = all_lines[-50:]
            except Exception:
                log_lines = ['(ログファイル読み取りエラー)']
        ctx['log_lines'] = log_lines

        ctx['title'] = 'デバッグパネル'
        ctx['has_permission'] = True
        ctx['site_header'] = getattr(settings, 'ADMIN_SITE_HEADER', 'Django administration')
        return ctx


class AdminDebugPanelAPIView(APIView):
    """AJAX endpoint for debug panel auto-refresh."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not request.user.is_authenticated or not (request.user.is_superuser or hasattr(request.user, 'staff') and request.user.staff.is_developer):
            return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        devices = IoTDevice.objects.filter(is_active=True).select_related('store')
        device_list = []
        for d in devices:
            online = False
            if d.last_seen_at:
                online = (now - d.last_seen_at).total_seconds() < 120
            device_list.append({
                'id': d.id,
                'name': d.name,
                'store': d.store.name,
                'external_id': d.external_id,
                'online': online,
                'last_seen_at': d.last_seen_at.isoformat() if d.last_seen_at else None,
            })

        events = IoTEvent.objects.select_related('device').order_by('-created_at')[:50]
        event_list = [{
            'id': e.id,
            'device': e.device.name,
            'event_type': e.event_type,
            'created_at': e.created_at.isoformat(),
            'mq9_value': e.mq9_value,
        } for e in events]

        return Response({'devices': device_list, 'events': event_list})


class LogLevelControlAPIView(APIView):
    """Dynamic log level control API."""
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)
        level = SystemConfig.get('log_level', settings.LOG_LEVEL)
        return Response({'log_level': level})

    def post(self, request):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return Response({'detail': 'forbidden'}, status=status.HTTP_403_FORBIDDEN)

        level = request.data.get('log_level', '').upper()
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if level not in valid_levels:
            return Response({'detail': f'Invalid level. Choose from: {valid_levels}'}, status=status.HTTP_400_BAD_REQUEST)

        # Persist to DB
        SystemConfig.set('log_level', level)

        # Apply to runtime loggers
        numeric_level = getattr(logging, level, logging.INFO)
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        for handler in root_logger.handlers:
            handler.setLevel(numeric_level)

        logger.info('Log level changed to %s', level)
        return Response({'log_level': level, 'applied': True})


class IoTDeviceDebugView(TemplateView):
    """Individual IoT device debug view."""
    template_name = 'admin/booking/iot_device_debug.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        device_id = self.kwargs.get('device_id')
        device = IoTDevice.objects.select_related('store').get(id=device_id)

        now = timezone.now()
        online = False
        if device.last_seen_at:
            online = (now - device.last_seen_at).total_seconds() < 120

        ctx['device'] = device
        ctx['online'] = online

        # Raw sensor data (last 100)
        events = IoTEvent.objects.filter(device=device).order_by('-created_at')[:100]
        event_data = []
        for e in events:
            payload_parsed = {}
            if e.payload:
                try:
                    payload_parsed = json.loads(e.payload)
                except Exception:
                    payload_parsed = {'_raw': e.payload}
            event_data.append({
                'id': e.id,
                'created_at': e.created_at,
                'event_type': e.event_type,
                'mq9_value': e.mq9_value,
                'light_value': e.light_value,
                'sound_value': e.sound_value,
                'pir_triggered': e.pir_triggered,
                'payload': payload_parsed,
            })
        ctx['events'] = event_data

        # Button/command events
        ctx['button_events'] = IoTEvent.objects.filter(
            device=device, event_type__startswith='button_'
        ).order_by('-created_at')[:20]

        ctx['title'] = f'デバイスデバッグ: {device.name}'
        ctx['has_permission'] = True
        return ctx
