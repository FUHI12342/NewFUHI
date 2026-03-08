"""Tests for debug panel views."""
import pytest
from django.test import Client
from django.urls import reverse

from booking.models import SystemConfig


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


class TestAdminDebugPanelView:
    """Tests for AdminDebugPanelView (developer/superuser only)."""

    @pytest.mark.django_db
    def test_debug_panel_forbidden_for_regular_user(self, authenticated_client):
        """Regular (non-admin) user cannot access debug panel."""
        resp = authenticated_client.get('/admin/debug/')
        # admin_view redirects non-admin users to login (302) or returns 403
        assert resp.status_code in (302, 403)

    @pytest.mark.django_db
    def test_debug_panel_accessible_by_admin(self, admin_client):
        """Admin/developer user can access debug panel."""
        resp = admin_client.get('/admin/debug/')
        # The admin_client has is_developer=True and is_superuser via conftest
        assert resp.status_code == 200


class TestLogLevelControlAPIView:
    """Tests for LogLevelControlAPIView."""

    @pytest.mark.django_db
    def test_get_log_level_requires_superuser(self, authenticated_client):
        """Non-superuser gets 403 from log level API."""
        resp = authenticated_client.get('/api/debug/log-level/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_set_invalid_log_level(self, admin_client, admin_user):
        """Setting invalid log level returns 400."""
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=admin_user)
        resp = client.post(
            '/api/debug/log-level/',
            data={'log_level': 'INVALID'},
            format='json',
        )
        assert resp.status_code == 400


class TestSystemConfigGetSet:
    """Tests for SystemConfig.get and SystemConfig.set (used by debug views)."""

    @pytest.mark.django_db
    def test_get_returns_default_for_missing_key(self):
        """SystemConfig.get returns default when key does not exist."""
        result = SystemConfig.get('nonexistent_key', 'default_value')
        assert result == 'default_value'

    @pytest.mark.django_db
    def test_set_creates_new_config(self):
        """SystemConfig.set creates a new config entry."""
        SystemConfig.set('test_key', 'test_value')
        assert SystemConfig.get('test_key') == 'test_value'

    @pytest.mark.django_db
    def test_set_updates_existing_config(self):
        """SystemConfig.set updates an existing config entry."""
        SystemConfig.set('update_key', 'old_value')
        SystemConfig.set('update_key', 'new_value')
        assert SystemConfig.get('update_key') == 'new_value'
