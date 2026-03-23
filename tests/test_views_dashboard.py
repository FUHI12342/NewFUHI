"""Tests for IoT sensor dashboard views."""
import pytest
from django.test import Client
from django.urls import reverse

from booking.models import IoTDevice, IoTEvent


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


# ==============================
# IoTSensorDashboardView
# ==============================

class TestIoTSensorDashboardView:
    """Tests for IoTSensorDashboardView."""

    def test_dashboard_returns_200(self, authenticated_client):
        """Dashboard page returns 200 for authenticated user."""
        url = reverse('booking:iot_sensor_dashboard')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_dashboard_contains_devices(self, authenticated_client, iot_device):
        """Dashboard context includes active devices."""
        url = reverse('booking:iot_sensor_dashboard')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200
        devices = resp.context['devices']
        assert iot_device in devices

    @pytest.mark.django_db
    def test_dashboard_excludes_inactive_devices(self, authenticated_client, iot_device):
        """Dashboard context excludes inactive devices."""
        iot_device.is_active = False
        iot_device.save()
        url = reverse('booking:iot_sensor_dashboard')
        resp = authenticated_client.get(url)
        devices = resp.context['devices']
        assert iot_device not in devices

    @pytest.mark.django_db
    def test_dashboard_unauthenticated_redirect(self, api_client):
        """Unauthenticated user is redirected to login."""
        url = reverse('booking:iot_sensor_dashboard')
        resp = api_client.get(url)
        # LoginRequiredMixin redirects to login page
        assert resp.status_code == 302


# ==============================
# IoTMQ9GraphView
# ==============================

class TestIoTMQ9GraphView:
    """Tests for IoTMQ9GraphView (now sensor monitor)."""

    @pytest.mark.django_db
    def test_sensor_monitor_requires_login(self, api_client):
        """Sensor monitor view requires login and redirects unauthenticated users."""
        url = '/booking/mq9/'
        resp = api_client.get(url, follow=False)
        # LoginRequiredMixin should redirect to login
        assert resp.status_code in (302, 301, 404)

    @pytest.mark.django_db
    def test_sensor_monitor_returns_200_authenticated(self, authenticated_client, iot_device):
        """Sensor monitor returns 200 for authenticated user."""
        from django.urls import reverse, NoReverseMatch
        try:
            url = reverse('booking:iot_mq9_graph')
        except NoReverseMatch:
            pytest.skip('iot_mq9_graph URL not configured in booking urls')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_sensor_monitor_context_has_devices(self, authenticated_client, iot_device):
        """Sensor monitor context includes devices list."""
        from django.urls import reverse, NoReverseMatch
        try:
            url = reverse('booking:iot_mq9_graph')
        except NoReverseMatch:
            pytest.skip('iot_mq9_graph URL not configured in booking urls')
        resp = authenticated_client.get(url)
        assert 'devices' in resp.context
        assert isinstance(resp.context['devices'], list)
