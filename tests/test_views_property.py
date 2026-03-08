"""Tests for property list and detail views."""
import pytest
from datetime import timedelta
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from booking.models import Property, PropertyDevice, PropertyAlert, IoTEvent


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


class TestPropertyListView:
    """Tests for PropertyListView."""

    @pytest.mark.django_db
    def test_list_returns_200(self, authenticated_client):
        """Property list page returns 200."""
        url = reverse('booking:property_list')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_list_contains_active_properties(self, authenticated_client, property_obj):
        """Property list includes active properties in context."""
        url = reverse('booking:property_list')
        resp = authenticated_client.get(url)
        properties = resp.context['properties']
        names = [p['name'] for p in properties]
        assert property_obj.name in names

    @pytest.mark.django_db
    def test_list_excludes_inactive_properties(self, authenticated_client, property_obj):
        """Property list excludes inactive properties."""
        property_obj.is_active = False
        property_obj.save()
        url = reverse('booking:property_list')
        resp = authenticated_client.get(url)
        properties = resp.context['properties']
        names = [p['name'] for p in properties]
        assert property_obj.name not in names

    @pytest.mark.django_db
    def test_list_shows_device_count(self, authenticated_client, property_obj, property_device):
        """Property list context includes device_count."""
        url = reverse('booking:property_list')
        resp = authenticated_client.get(url)
        prop_data = resp.context['properties'][0]
        assert prop_data['device_count'] == 1

    @pytest.mark.django_db
    def test_list_shows_alert_count(self, authenticated_client, property_obj):
        """Property list context includes alert_count."""
        PropertyAlert.objects.create(
            property=property_obj,
            alert_type='gas_leak',
            severity='critical',
            message='Gas detected',
        )
        url = reverse('booking:property_list')
        resp = authenticated_client.get(url)
        prop_data = resp.context['properties'][0]
        assert prop_data['alert_count'] == 1
        assert prop_data['critical_count'] == 1


class TestPropertyDetailView:
    """Tests for PropertyDetailView."""

    @pytest.mark.django_db
    def test_detail_returns_200(self, authenticated_client, property_obj):
        """Property detail page returns 200."""
        url = reverse('booking:property_detail', kwargs={'pk': property_obj.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_detail_context_has_property_info(self, authenticated_client, property_obj):
        """Property detail context contains property information."""
        url = reverse('booking:property_detail', kwargs={'pk': property_obj.pk})
        resp = authenticated_client.get(url)
        prop = resp.context['property']
        assert prop['name'] == property_obj.name
        assert prop['address'] == property_obj.address

    @pytest.mark.django_db
    def test_detail_shows_devices(self, authenticated_client, property_obj, property_device):
        """Property detail context includes devices list."""
        url = reverse('booking:property_detail', kwargs={'pk': property_obj.pk})
        resp = authenticated_client.get(url)
        devices = resp.context['devices']
        assert len(devices) == 1
        assert devices[0]['location_label'] == property_device.location_label

    @pytest.mark.django_db
    def test_detail_shows_active_alerts(self, authenticated_client, property_obj):
        """Property detail context includes active (unresolved) alerts."""
        alert = PropertyAlert.objects.create(
            property=property_obj,
            alert_type='device_offline',
            severity='warning',
            message='Device went offline',
        )
        url = reverse('booking:property_detail', kwargs={'pk': property_obj.pk})
        resp = authenticated_client.get(url)
        assert alert in resp.context['active_alerts']

    @pytest.mark.django_db
    def test_detail_resolved_alerts_separate(self, authenticated_client, property_obj):
        """Resolved alerts appear in resolved_alerts, not active_alerts."""
        alert = PropertyAlert.objects.create(
            property=property_obj,
            alert_type='gas_leak',
            severity='critical',
            message='Resolved gas issue',
            is_resolved=True,
            resolved_at=timezone.now(),
        )
        url = reverse('booking:property_detail', kwargs={'pk': property_obj.pk})
        resp = authenticated_client.get(url)
        assert alert not in resp.context['active_alerts']
        assert alert in resp.context['resolved_alerts']
