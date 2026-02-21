# booking/views_property.py
import json
import logging
from datetime import timedelta

from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import Property, PropertyDevice, PropertyAlert, IoTEvent

logger = logging.getLogger(__name__)


class PropertyListView(TemplateView):
    """Property list with status summary."""
    template_name = 'booking/property_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        properties = Property.objects.filter(is_active=True)

        prop_list = []
        for p in properties:
            pds = PropertyDevice.objects.filter(property=p).select_related('device')
            device_count = pds.count()
            online_count = sum(
                1 for pd in pds
                if pd.device.last_seen_at and (now - pd.device.last_seen_at).total_seconds() < 120
            )
            active_alerts = PropertyAlert.objects.filter(property=p, is_resolved=False)
            alert_count = active_alerts.count()
            critical_count = active_alerts.filter(severity='critical').count()

            prop_list.append({
                'id': p.id,
                'name': p.name,
                'address': p.address,
                'property_type': p.get_property_type_display(),
                'device_count': device_count,
                'online_count': online_count,
                'alert_count': alert_count,
                'critical_count': critical_count,
            })

        ctx['properties'] = prop_list
        return ctx


class PropertyDetailView(TemplateView):
    """Property detail dashboard."""
    template_name = 'booking/property_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        now = timezone.now()
        prop = Property.objects.get(pk=self.kwargs['pk'])

        pds = PropertyDevice.objects.filter(property=prop).select_related('device')
        devices = []
        occupied = False
        for pd in pds:
            d = pd.device
            online = bool(d.last_seen_at and (now - d.last_seen_at).total_seconds() < 120)

            # Latest sensor values
            latest = IoTEvent.objects.filter(device=d).order_by('-created_at').first()
            latest_mq9 = latest.mq9_value if latest else None
            latest_light = latest.light_value if latest else None
            latest_sound = latest.sound_value if latest else None

            # PIR in last 30 min
            pir_recent = IoTEvent.objects.filter(
                device=d, pir_triggered=True,
                created_at__gte=now - timedelta(minutes=30),
            ).exists()
            if pir_recent:
                occupied = True

            devices.append({
                'id': d.id,
                'name': d.name,
                'location_label': pd.location_label,
                'online': online,
                'latest_mq9': latest_mq9,
                'latest_light': latest_light,
                'latest_sound': latest_sound,
                'pir_recent': pir_recent,
            })

        active_alerts = PropertyAlert.objects.filter(
            property=prop, is_resolved=False,
        ).order_by('-created_at')
        resolved_alerts = PropertyAlert.objects.filter(
            property=prop, is_resolved=True,
        ).order_by('-created_at')[:20]

        ctx['property'] = {
            'id': prop.id,
            'name': prop.name,
            'address': prop.address,
            'property_type': prop.get_property_type_display(),
            'owner': prop.owner_name,
            'occupied': occupied,
        }
        ctx['devices'] = devices
        ctx['active_alerts'] = active_alerts
        ctx['resolved_alerts'] = resolved_alerts
        return ctx


class PropertyStatusAPIView(APIView):
    """AJAX endpoint for property detail auto-refresh."""
    authentication_classes = []
    permission_classes = []

    def get(self, request, pk):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        try:
            prop = Property.objects.get(pk=pk)
        except Property.DoesNotExist:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)

        pds = PropertyDevice.objects.filter(property=prop).select_related('device')
        devices = []
        occupied = False
        for pd in pds:
            d = pd.device
            online = bool(d.last_seen_at and (now - d.last_seen_at).total_seconds() < 120)
            latest = IoTEvent.objects.filter(device=d).order_by('-created_at').first()
            pir_recent = IoTEvent.objects.filter(
                device=d, pir_triggered=True,
                created_at__gte=now - timedelta(minutes=30),
            ).exists()
            if pir_recent:
                occupied = True
            devices.append({
                'id': d.id,
                'name': d.name,
                'location_label': pd.location_label,
                'online': online,
                'latest_mq9': latest.mq9_value if latest else None,
                'latest_light': latest.light_value if latest else None,
                'latest_sound': latest.sound_value if latest else None,
                'pir_recent': pir_recent,
            })

        alerts = list(PropertyAlert.objects.filter(
            property=prop, is_resolved=False,
        ).order_by('-created_at').values('id', 'severity', 'alert_type', 'message', 'created_at'))
        for a in alerts:
            a['created_at'] = a['created_at'].isoformat()

        return Response({'devices': devices, 'alerts': alerts, 'occupied': occupied})


class PropertyAlertResolveAPIView(APIView):
    """POST /api/alerts/<id>/resolve/ — mark an alert as resolved."""
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return Response({'detail': 'login required'}, status=status.HTTP_403_FORBIDDEN)
        try:
            alert = PropertyAlert.objects.get(pk=pk)
        except PropertyAlert.DoesNotExist:
            return Response({'detail': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        alert.is_resolved = True
        alert.resolved_at = timezone.now()
        alert.save(update_fields=['is_resolved', 'resolved_at'])
        return Response({'resolved': True})
