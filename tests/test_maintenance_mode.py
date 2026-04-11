"""
tests/test_maintenance_mode.py
Tests for MaintenanceMiddleware:
  - 503 for anonymous users when maintenance ON
  - is_staff users bypass maintenance
  - normal access when maintenance OFF
  - /healthz bypasses maintenance
  - /admin/login bypasses maintenance
"""
import pytest
from django.test import Client

from booking.models import SiteSettings


@pytest.fixture
def site_settings_maintenance(db):
    """SiteSettings with maintenance ON."""
    from django.core.cache import cache
    cache.delete('site_settings_singleton')
    s = SiteSettings.load()
    s.maintenance_mode = True
    s.maintenance_message = 'テスト中です'
    s.save()
    return s


class TestMaintenanceMiddleware:

    @pytest.mark.django_db
    def test_anonymous_gets_503_when_maintenance_on(self, site_settings_maintenance):
        client = Client()
        resp = client.get('/')
        assert resp.status_code == 503
        assert 'メンテナンス中' in resp.content.decode()
        assert 'テスト中です' in resp.content.decode()
        assert resp['Retry-After'] == '300'

    @pytest.mark.django_db
    def test_staff_bypasses_maintenance(self, site_settings_maintenance, staff_user):
        client = Client()
        client.login(username='staffuser', password='staffpass123')
        resp = client.get('/')
        assert resp.status_code != 503

    @pytest.mark.django_db
    def test_normal_access_when_off(self, db):
        from django.core.cache import cache
        cache.delete('site_settings_singleton')
        s = SiteSettings.load()
        s.maintenance_mode = False
        s.save()
        client = Client()
        resp = client.get('/')
        assert resp.status_code != 503

    @pytest.mark.django_db
    def test_healthz_bypasses_maintenance(self, site_settings_maintenance):
        client = Client()
        resp = client.get('/healthz')
        assert resp.status_code != 503

    @pytest.mark.django_db
    def test_admin_login_bypasses_maintenance(self, site_settings_maintenance):
        client = Client()
        resp = client.get('/admin/login/')
        assert resp.status_code != 503
