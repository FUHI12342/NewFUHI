# booking/views_dashboard.py
import json
import logging
from datetime import timedelta

from django.db.models import Avg
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import IoTDevice, IoTEvent

logger = logging.getLogger(__name__)


class IoTSensorDashboardView(TemplateView):
    """Task-manager style IoT sensor dashboard."""
    template_name = 'booking/iot_sensor_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['devices'] = IoTDevice.objects.filter(is_active=True).select_related('store')
        return ctx


class SensorDataAPIView(APIView):
    """GET /api/iot/sensors/data/ — time-series sensor data for Chart.js."""
    authentication_classes = []
    permission_classes = []

    RANGE_MAP = {
        '1h': timedelta(hours=1),
        '6h': timedelta(hours=6),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
    }
    MAX_POINTS = 500

    def get(self, request):
        # List devices mode
        if request.GET.get('list_devices'):
            devices = IoTDevice.objects.filter(is_active=True).values('id', 'name', 'external_id')
            return Response({'devices': list(devices)})

        device_id = request.GET.get('device_id')
        if not device_id:
            return Response({'detail': 'device_id required'}, status=status.HTTP_400_BAD_REQUEST)

        time_range = request.GET.get('range', '1h')
        sensor = request.GET.get('sensor', 'mq9')
        td = self.RANGE_MAP.get(time_range, timedelta(hours=1))
        since = timezone.now() - td

        # Map sensor name to model field
        field_map = {
            'mq9': 'mq9_value',
            'light': 'light_value',
            'sound': 'sound_value',
        }
        field = field_map.get(sensor, 'mq9_value')

        qs = IoTEvent.objects.filter(
            device_id=device_id,
            created_at__gte=since,
        ).exclude(**{f'{field}__isnull': True}).order_by('created_at').values_list('created_at', field)

        data = list(qs)

        # Downsample if too many points
        if len(data) > self.MAX_POINTS:
            step = len(data) // self.MAX_POINTS
            data = data[::step]

        labels = [d[0].isoformat() for d in data]
        values = [d[1] for d in data]

        return Response({'labels': labels, 'values': values})


class PIREventsAPIView(APIView):
    """GET /api/iot/sensors/pir-events/ — PIR motion events bucketed by hour."""
    authentication_classes = []
    permission_classes = []

    RANGE_MAP = {
        '1h': timedelta(hours=1),
        '6h': timedelta(hours=6),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
    }

    def get(self, request):
        device_id = request.GET.get('device_id')
        if not device_id:
            return Response({'detail': 'device_id required'}, status=status.HTTP_400_BAD_REQUEST)

        time_range = request.GET.get('range', '1h')
        td = self.RANGE_MAP.get(time_range, timedelta(hours=1))
        since = timezone.now() - td

        events = IoTEvent.objects.filter(
            device_id=device_id,
            created_at__gte=since,
            pir_triggered=True,
        ).order_by('created_at').values_list('created_at', flat=True)

        # Bucket by hour
        buckets = {}
        for dt in events:
            key = dt.replace(minute=0, second=0, microsecond=0)
            buckets[key] = buckets.get(key, 0) + 1

        sorted_keys = sorted(buckets.keys())
        labels = [k.isoformat() for k in sorted_keys]
        counts = [buckets[k] for k in sorted_keys]

        return Response({'labels': labels, 'counts': counts})
