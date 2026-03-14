"""
Phase 5b: カバレッジ補足テスト — 80% 到達用

対象:
  - booking/views_chat.py: AdminChatAPIView (0% → ~90%)
  - booking/forms.py: _build_model_choices, AdminMenuConfigForm (47% → ~90%)
  - booking/context_processors.py: global_context, admin_user_flags, admin_theme (70% → ~95%)
  - booking/views_dashboard.py: SensorDataAPIView, PIRStatusAPIView, PIREventsAPIView (74% → ~95%)
  - booking/views_property.py: PropertyStatusAPIView, PropertyAlertResolveAPIView (65% → ~85%)
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import (
    Store, Staff, IoTDevice, IoTEvent, Property, PropertyDevice, PropertyAlert,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_s(db):
    return Store.objects.create(
        name="補足テスト店舗", address="東京", business_hours="10-22",
        nearest_station="新宿",
    )


@pytest.fixture
def su_user(store_s):
    user = User.objects.create_superuser(
        username="supp_su", password="pass123", email="supp_su@test.com",
    )
    Staff.objects.create(name="補足管理者", store=store_s, user=user, is_developer=True)
    return user


@pytest.fixture
def su_client(su_user):
    client = Client()
    client.login(username="supp_su", password="pass123")
    return client


@pytest.fixture
def su_api(su_user):
    client = APIClient()
    client.force_authenticate(user=su_user)
    return client


@pytest.fixture
def staff_user_s(store_s):
    user = User.objects.create_user(
        username="supp_staff", password="pass123", email="supp_staff@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="補足スタッフ", store=store_s, user=user)
    return user


@pytest.fixture
def device_s(store_s):
    import hashlib
    raw = "test-key-supp"
    return IoTDevice.objects.create(
        name="補足デバイス", store=store_s, device_type="multi",
        external_id="supp-001",
        api_key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        api_key_prefix=raw[:8],
        is_active=True,
    )


# ==============================
# AdminChatAPIView tests
# ==============================

class TestAdminChatAPI:
    """booking.views_chat.AdminChatAPIView (tested via RequestFactory)."""

    def _post(self, user, body):
        from booking.views_chat import AdminChatAPIView
        factory = RequestFactory()
        request = factory.post(
            '/api/chat/admin/',
            json.dumps(body),
            content_type='application/json',
        )
        request.user = user
        view = AdminChatAPIView.as_view()
        return view(request)

    def test_unauthenticated(self, db):
        from django.contrib.auth.models import AnonymousUser
        resp = self._post(AnonymousUser(), {'message': 'hello'})
        assert resp.status_code == 403

    def test_non_staff(self, store_s):
        user = User.objects.create_user(
            username="nonstaff_chat", password="pass", email="ns@test.com",
        )
        resp = self._post(user, {'message': 'hello'})
        assert resp.status_code == 403

    def test_invalid_json(self, su_user):
        from booking.views_chat import AdminChatAPIView
        factory = RequestFactory()
        request = factory.post(
            '/api/chat/admin/',
            'not json!!!',
            content_type='application/json',
        )
        request.user = su_user
        resp = AdminChatAPIView.as_view()(request)
        assert resp.status_code == 400

    def test_empty_message(self, su_user):
        resp = self._post(su_user, {'message': ''})
        assert resp.status_code == 400

    @patch('booking.views_chat.cache')
    def test_rate_limit(self, mock_cache, su_user):
        import time
        # Simulate 20 timestamps all within the window
        mock_cache.get.return_value = [time.time()] * 20
        resp = self._post(su_user, {'message': 'hello'})
        assert resp.status_code == 429

    @patch('booking.services.ai_chat.AdminChatService')
    @patch('booking.views_chat.cache')
    def test_success(self, mock_cache, mock_service_cls, su_user):
        mock_cache.get.return_value = []
        mock_service = MagicMock()
        mock_service.get_response.return_value = 'AI回答です'
        mock_service_cls.return_value = mock_service

        resp = self._post(su_user, {'message': 'こんにちは'})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['reply'] == 'AI回答です'
        mock_cache.set.assert_called_once()


# ==============================
# forms tests
# ==============================

class TestBuildModelChoices:
    """booking.forms._build_model_choices"""

    def test_returns_choices(self):
        from booking.forms import _build_model_choices
        choices = _build_model_choices()
        assert len(choices) > 0
        # Each choice is (key, label)
        for key, label in choices:
            assert isinstance(key, str)
            assert isinstance(label, str)

    def test_no_duplicates(self):
        from booking.forms import _build_model_choices
        choices = _build_model_choices()
        keys = [k for k, _ in choices]
        assert len(keys) == len(set(keys))


class TestAdminMenuConfigForm:
    """booking.forms.AdminMenuConfigForm"""

    def test_form_init(self):
        from booking.forms import AdminMenuConfigForm
        form = AdminMenuConfigForm()
        # choices should be populated
        assert len(form.fields['allowed_models'].choices) > 0

    def test_form_with_instance(self, db):
        from booking.forms import AdminMenuConfigForm
        from booking.models import AdminMenuConfig
        cfg = AdminMenuConfig.objects.create(
            role='owner',
            allowed_models=['staff', 'store'],
        )
        form = AdminMenuConfigForm(instance=cfg)
        assert form.initial['allowed_models'] == ['staff', 'store']


# ==============================
# context_processors tests
# ==============================

class TestContextProcessors:
    """booking.context_processors"""

    def test_global_context(self, su_client):
        from booking.context_processors import global_context
        factory = RequestFactory()
        request = factory.get('/')
        ctx = global_context(request)
        assert 'stores' in ctx
        assert 'site_settings' in ctx
        assert 'staff_label' in ctx

    def test_global_context_cached(self, su_client):
        from booking.context_processors import global_context
        factory = RequestFactory()
        request = factory.get('/')
        ctx1 = global_context(request)
        ctx2 = global_context(request)
        assert ctx1 == ctx2

    def test_admin_user_flags_non_admin_path(self):
        from booking.context_processors import admin_user_flags
        factory = RequestFactory()
        request = factory.get('/booking/')
        request.user = MagicMock(is_authenticated=True, is_superuser=True)
        result = admin_user_flags(request)
        assert result == {}

    def test_admin_user_flags_superuser(self, su_user):
        from booking.context_processors import admin_user_flags
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = su_user
        result = admin_user_flags(request)
        assert result['is_developer_or_superuser'] is True

    def test_admin_user_flags_regular(self, staff_user_s):
        from booking.context_processors import admin_user_flags
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = staff_user_s
        result = admin_user_flags(request)
        assert result['is_developer_or_superuser'] is False

    def test_admin_user_flags_with_lang_prefix(self, su_user):
        from booking.context_processors import admin_user_flags
        factory = RequestFactory()
        request = factory.get('/en/admin/')
        request.user = su_user
        result = admin_user_flags(request)
        assert result['is_developer_or_superuser'] is True

    def test_admin_theme_non_admin(self):
        from booking.context_processors import admin_theme
        factory = RequestFactory()
        request = factory.get('/booking/')
        result = admin_theme(request)
        assert result == {}

    def test_admin_theme_unauthenticated(self):
        from booking.context_processors import admin_theme
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = MagicMock(is_authenticated=False)
        result = admin_theme(request)
        assert result == {}

    def test_admin_theme_no_staff(self, db):
        from booking.context_processors import admin_theme
        user = User.objects.create_user(
            username="noprof", password="pass", email="noprof@test.com",
        )
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = user
        result = admin_theme(request)
        assert result == {}

    def test_localized_staff_label_ja(self, db):
        from booking.context_processors import _get_localized_staff_label
        from booking.models import SiteSettings
        ss = SiteSettings.load()
        ss.staff_label = 'キャスト'
        ss.staff_label_i18n = {'en': 'Cast', 'zh-hant': '演員'}
        ss.save()
        with patch('booking.context_processors.get_language', return_value='ja'):
            assert _get_localized_staff_label(ss) == 'キャスト'

    def test_localized_staff_label_en(self, db):
        from booking.context_processors import _get_localized_staff_label
        from booking.models import SiteSettings
        ss = SiteSettings.load()
        ss.staff_label = 'キャスト'
        ss.staff_label_i18n = {'en': 'Cast', 'zh-hant': '演員'}
        ss.save()
        with patch('booking.context_processors.get_language', return_value='en'):
            assert _get_localized_staff_label(ss) == 'Cast'

    def test_localized_staff_label_fallback(self, db):
        from booking.context_processors import _get_localized_staff_label
        from booking.models import SiteSettings
        ss = SiteSettings.load()
        ss.staff_label = 'キャスト'
        ss.staff_label_i18n = {'zh': '演員'}
        ss.save()
        with patch('booking.context_processors.get_language', return_value='zh-hant'):
            # Falls back to base language 'zh'
            assert _get_localized_staff_label(ss) == '演員'


# ==============================
# SensorDataAPIView tests
# ==============================

class TestSensorDataAPI:
    URL = '/api/iot/sensors/data/'

    def test_list_devices(self, su_api, device_s):
        resp = su_api.get(self.URL + '?list_devices=1')
        assert resp.status_code == 200
        assert len(resp.json()['devices']) >= 1

    def test_missing_device_id(self, su_api):
        resp = su_api.get(self.URL)
        assert resp.status_code == 400

    def test_by_device_pk(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="sensor", mq9_value=300.0)
        resp = su_api.get(self.URL + f'?device_id={device_s.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert 'labels' in data
        assert 'values' in data

    def test_by_external_id(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="sensor", mq9_value=200.0)
        resp = su_api.get(self.URL + f'?device_id={device_s.external_id}')
        assert resp.status_code == 200

    def test_sensor_param(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="sensor", light_value=500)
        resp = su_api.get(self.URL + f'?device_id={device_s.id}&sensor=light')
        assert resp.status_code == 200

    def test_range_param(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="sensor", mq9_value=100.0)
        resp = su_api.get(self.URL + f'?device_id={device_s.id}&range=24h')
        assert resp.status_code == 200


# ==============================
# PIRStatusAPIView tests
# ==============================

class TestPIRStatusAPI:
    URL = '/api/iot/sensors/pir-status/'

    def test_missing_device_id(self, su_api):
        resp = su_api.get(self.URL)
        assert resp.status_code == 400

    def test_no_recent_pir(self, su_api, device_s):
        resp = su_api.get(self.URL + f'?device_id={device_s.id}')
        assert resp.status_code == 200
        assert resp.json()['active'] is False

    def test_with_recent_pir(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="pir", pir_triggered=True)
        resp = su_api.get(self.URL + f'?device_id={device_s.id}')
        assert resp.status_code == 200
        assert resp.json()['active'] is True


# ==============================
# PIREventsAPIView tests
# ==============================

class TestPIREventsAPI:
    URL = '/api/iot/sensors/pir-events/'

    def test_missing_device_id(self, su_api):
        resp = su_api.get(self.URL)
        assert resp.status_code == 400

    def test_empty(self, su_api, device_s):
        resp = su_api.get(self.URL + f'?device_id={device_s.id}')
        assert resp.status_code == 200
        assert resp.json()['labels'] == []

    def test_with_events(self, su_api, device_s):
        IoTEvent.objects.create(device=device_s, event_type="pir", pir_triggered=True)
        resp = su_api.get(self.URL + f'?device_id={device_s.id}&range=1h')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['labels']) >= 1
        assert data['counts'][0] >= 1


# ==============================
# PropertyStatusAPIView tests
# ==============================

class TestPropertyStatusAPI:

    def test_unauthenticated(self, db):
        client = APIClient()
        resp = client.get('/api/properties/999/status/')
        assert resp.status_code == 403

    def test_not_found(self, su_api):
        resp = su_api.get('/api/properties/999/status/')
        assert resp.status_code == 404

    def test_success(self, su_api, store_s, device_s):
        prop = Property.objects.create(
            name="テスト物件", address="渋谷", property_type='apartment',
            store=store_s, is_active=True,
        )
        PropertyDevice.objects.create(
            property=prop, device=device_s, location_label="リビング",
        )
        resp = su_api.get(f'/api/properties/{prop.pk}/status/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'devices' in data
        assert 'alerts' in data


# ==============================
# PropertyAlertResolveAPIView tests
# ==============================

class TestPropertyAlertResolveAPI:

    def test_unauthenticated(self, db):
        client = APIClient()
        resp = client.post('/api/alerts/999/resolve/')
        assert resp.status_code == 403

    def test_not_found(self, su_api):
        resp = su_api.post('/api/alerts/999/resolve/')
        assert resp.status_code == 404

    def test_resolve_alert(self, su_api, store_s):
        prop = Property.objects.create(
            name="物件X", address="渋谷", property_type='apartment',
            store=store_s, is_active=True,
        )
        alert = PropertyAlert.objects.create(
            property=prop, severity='warning', alert_type='gas',
            message='ガス検知', is_resolved=False,
        )
        resp = su_api.post(f'/api/alerts/{alert.pk}/resolve/')
        assert resp.status_code == 200
        assert resp.json()['resolved'] is True
        alert.refresh_from_db()
        assert alert.is_resolved is True
