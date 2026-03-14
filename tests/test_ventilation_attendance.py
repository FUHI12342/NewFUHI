"""
Phase 5: 換気制御・勤怠・デバッグのテスト

対象:
  - booking/ventilation_control.py: _switchbot_headers, switchbot_command, check_ventilation_rules
  - booking/views_attendance.py: AttendancePINStampAPIView, AttendanceTOTPRefreshAPI
  - booking/views_debug.py: AdminDebugPanelAPIView, LogLevelControlAPIView, IoTDeviceDebugView
"""
import json
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import (
    Store, Staff, IoTDevice, IoTEvent, VentilationAutoControl,
    AttendanceTOTPConfig, AttendanceStamp, WorkAttendance, SystemConfig,
)
from booking.ventilation_control import (
    _switchbot_headers, switchbot_command, check_ventilation_rules,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_v(db):
    return Store.objects.create(
        name="換気テスト店舗", address="東京", business_hours="10-22",
        nearest_station="渋谷",
    )


@pytest.fixture
def device(store_v):
    import hashlib
    raw = "test-key-vent"
    return IoTDevice.objects.create(
        name="換気デバイス", store=store_v, device_type="multi",
        external_id="vent-001",
        api_key_hash=hashlib.sha256(raw.encode()).hexdigest(),
        api_key_prefix=raw[:8],
    )


@pytest.fixture
def vent_rule(device):
    rule = VentilationAutoControl.objects.create(
        device=device,
        name="テストルール",
        is_active=True,
        threshold_on=400,
        threshold_off=200,
        consecutive_count=3,
        switchbot_device_id="PLUG001",
        cooldown_seconds=60,
        fan_state="off",
    )
    rule.set_switchbot_token("test-token")
    rule.set_switchbot_secret("test-secret")
    rule.save()
    return rule


@pytest.fixture
def su_client(store_v):
    user = User.objects.create_superuser(
        username="vent_su", password="pass123", email="vsu@test.com",
    )
    Staff.objects.create(name="管理者V", store=store_v, user=user, is_developer=True)
    client = Client()
    client.login(username="vent_su", password="pass123")
    return client


@pytest.fixture
def staff_with_pin(store_v):
    user = User.objects.create_user(
        username="pin_staff", password="pass123", email="pin@test.com",
        is_staff=True,
    )
    s = Staff.objects.create(name="PINスタッフ", store=store_v, user=user)
    s.set_attendance_pin("1234")
    s.save()
    return s


@pytest.fixture
def staff_no_pin(store_v):
    user = User.objects.create_user(
        username="nopin_staff", password="pass123", email="nopin@test.com",
        is_staff=True,
    )
    return Staff.objects.create(name="PIN未設定", store=store_v, user=user)


@pytest.fixture
def su_api_client(store_v):
    """DRF APIClient for superuser (needed for views with authentication_classes=[])."""
    user = User.objects.create_superuser(
        username="vent_su_api", password="pass123", email="vsuapi@test.com",
    )
    Staff.objects.create(name="管理者API", store=store_v, user=user, is_developer=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def totp_cfg(store_v):
    from booking.services.totp_service import generate_totp_secret
    return AttendanceTOTPConfig.objects.create(
        store=store_v,
        totp_secret=generate_totp_secret(),
        totp_interval=30,
        is_active=True,
    )


# ==============================
# _switchbot_headers tests
# ==============================

class TestSwitchbotHeaders:

    @patch('booking.ventilation_control.uuid')
    @patch('booking.ventilation_control.time')
    def test_headers_format(self, mock_time, mock_uuid):
        mock_time.time.return_value = 1700000000.0
        mock_uuid.uuid4.return_value = MagicMock(hex="abc123")

        headers = _switchbot_headers("my-token", "my-secret")

        assert headers["Authorization"] == "my-token"
        assert headers["t"] == "1700000000000"
        assert headers["nonce"] == "abc123"
        assert headers["Content-Type"] == "application/json"
        assert "sign" in headers
        assert len(headers["sign"]) > 0


# ==============================
# switchbot_command tests
# ==============================

class TestSwitchbotCommand:

    @patch('booking.ventilation_control.requests.post')
    def test_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"statusCode": 100, "message": "success"}
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = switchbot_command("tok", "sec", "DEV001", "turnOn")

        assert result["statusCode"] == 100
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "DEV001" in call_args[0][0]
        assert call_args[1]["json"]["command"] == "turnOn"

    @patch('booking.ventilation_control.requests.post')
    def test_failure_raises(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        mock_post.return_value = mock_resp

        with pytest.raises(Exception, match="HTTP 500"):
            switchbot_command("tok", "sec", "DEV001", "turnOn")


# ==============================
# check_ventilation_rules tests
# ==============================

class TestCheckVentilationRules:

    def test_no_active_rules(self, device):
        """No active rules → returns without action."""
        check_ventilation_rules(device, 500.0)
        # No error raised

    def test_cooldown_active(self, device, vent_rule):
        """Rule in cooldown → skip."""
        vent_rule.last_on_at = timezone.now()
        vent_rule.save()

        with patch('booking.ventilation_control.switchbot_command') as mock_cmd:
            check_ventilation_rules(device, 500.0)
            mock_cmd.assert_not_called()

    @patch('booking.ventilation_control.switchbot_command')
    def test_on_trigger(self, mock_cmd, device, vent_rule):
        """Consecutive readings above threshold → turn ON."""
        mock_cmd.return_value = {"statusCode": 100}
        # Create consecutive events above threshold
        for i in range(3):
            IoTEvent.objects.create(
                device=device, event_type="sensor",
                mq9_value=500.0,
            )

        check_ventilation_rules(device, 500.0)

        mock_cmd.assert_called_once()
        assert mock_cmd.call_args[0][3] == "turnOn"
        vent_rule.refresh_from_db()
        assert vent_rule.fan_state == "on"
        assert vent_rule.last_on_at is not None

    @patch('booking.ventilation_control.switchbot_command')
    def test_on_not_enough_consecutive(self, mock_cmd, device, vent_rule):
        """Not enough consecutive readings → no trigger."""
        # Only 2 events (rule requires 3)
        IoTEvent.objects.create(device=device, event_type="sensor", mq9_value=500.0)
        IoTEvent.objects.create(device=device, event_type="sensor", mq9_value=500.0)

        check_ventilation_rules(device, 500.0)
        mock_cmd.assert_not_called()

    @patch('booking.ventilation_control.switchbot_command')
    def test_off_trigger(self, mock_cmd, device, vent_rule):
        """Value below threshold_off and fan is ON → turn OFF."""
        mock_cmd.return_value = {"statusCode": 100}
        vent_rule.fan_state = "on"
        vent_rule.save()

        check_ventilation_rules(device, 100.0)

        mock_cmd.assert_called_once()
        assert mock_cmd.call_args[0][3] == "turnOff"
        vent_rule.refresh_from_db()
        assert vent_rule.fan_state == "off"
        assert vent_rule.last_off_at is not None

    @patch('booking.ventilation_control.switchbot_command')
    def test_on_failure_applies_cooldown(self, mock_cmd, device, vent_rule):
        """SwitchBot failure on turnOn → cooldown applied."""
        mock_cmd.side_effect = Exception("API error")
        for i in range(3):
            IoTEvent.objects.create(device=device, event_type="sensor", mq9_value=500.0)

        check_ventilation_rules(device, 500.0)

        vent_rule.refresh_from_db()
        # fan_state stays off, but last_on_at set for cooldown
        assert vent_rule.fan_state == "off"
        assert vent_rule.last_on_at is not None

    @patch('booking.ventilation_control.switchbot_command')
    def test_off_failure_applies_cooldown(self, mock_cmd, device, vent_rule):
        """SwitchBot failure on turnOff → cooldown applied."""
        mock_cmd.side_effect = Exception("API error")
        vent_rule.fan_state = "on"
        vent_rule.save()

        check_ventilation_rules(device, 100.0)

        vent_rule.refresh_from_db()
        # fan_state stays on, but last_off_at set for cooldown
        assert vent_rule.fan_state == "on"
        assert vent_rule.last_off_at is not None


# ==============================
# AttendancePINStampAPIView tests
# ==============================

class TestAttendancePINStampAPI:
    URL = '/api/attendance/pin-stamp/'

    def test_unauthenticated(self):
        client = Client()
        resp = client.post(self.URL, '{}', content_type='application/json')
        # LoginRequired → redirect to login
        assert resp.status_code == 302

    def test_missing_staff_id(self, su_client):
        resp = su_client.post(
            self.URL,
            json.dumps({'pin': '1234'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'staff_id' in resp.json()['error']

    def test_missing_pin(self, su_client, staff_with_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({'staff_id': staff_with_pin.id}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'PIN' in resp.json()['error']

    def test_pin_not_set(self, su_client, staff_no_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({'staff_id': staff_no_pin.id, 'pin': '9999'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '未設定' in resp.json()['error']

    def test_wrong_pin(self, su_client, staff_with_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({'staff_id': staff_with_pin.id, 'pin': '0000'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '正しくありません' in resp.json()['error']

    @patch('booking.services.totp_service.check_duplicate_stamp', return_value=True)
    def test_duplicate_stamp(self, mock_dup, su_client, staff_with_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({'staff_id': staff_with_pin.id, 'pin': '1234'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '5分以内' in resp.json()['error']

    @patch('booking.services.totp_service.check_duplicate_stamp', return_value=False)
    def test_clock_in_success(self, mock_dup, su_client, staff_with_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert data['staff_name'] == 'PINスタッフ'
        assert data['stamp_type'] == 'clock_in'
        # Verify stamp and attendance created
        assert AttendanceStamp.objects.filter(staff=staff_with_pin).exists()
        att = WorkAttendance.objects.get(staff=staff_with_pin)
        assert att.source == 'pin'
        assert att.clock_in is not None

    @patch('booking.services.totp_service.check_duplicate_stamp', return_value=False)
    def test_clock_out_success(self, mock_dup, su_client, staff_with_pin):
        resp = su_client.post(
            self.URL,
            json.dumps({
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'stamp_type': 'clock_out',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['stamp_type'] == 'clock_out'
        att = WorkAttendance.objects.get(staff=staff_with_pin)
        assert att.clock_out is not None

    @patch('booking.services.totp_service.check_geo_fence', return_value=False)
    @patch('booking.services.totp_service.check_duplicate_stamp', return_value=False)
    def test_geo_fence_fail(self, mock_dup, mock_geo, su_client, staff_with_pin, totp_cfg):
        totp_cfg.require_geo_check = True
        totp_cfg.location_lat = 35.6762
        totp_cfg.location_lng = 139.6503
        totp_cfg.geo_fence_radius_m = 100
        totp_cfg.save()

        resp = su_client.post(
            self.URL,
            json.dumps({
                'staff_id': staff_with_pin.id,
                'pin': '1234',
                'latitude': 34.0,
                'longitude': 135.0,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '範囲外' in resp.json()['error']

    def test_invalid_json(self, su_client):
        resp = su_client.post(
            self.URL,
            'not json',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'Invalid JSON' in resp.json()['error']


# ==============================
# AttendanceTOTPRefreshAPI tests
# ==============================

class TestAttendanceTOTPRefreshAPI:
    URL = '/api/attendance/totp/refresh/'

    def test_unauthenticated(self):
        client = Client()
        resp = client.get(self.URL)
        assert resp.status_code == 302

    def test_no_totp_config(self, su_client):
        resp = su_client.get(self.URL)
        assert resp.status_code == 404
        assert 'TOTP not configured' in resp.json()['error']

    def test_with_totp_config(self, su_client, totp_cfg):
        resp = su_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert 'code' in data
        assert data['interval'] == 30
        assert len(data['code']) > 0


# ==============================
# AdminDebugPanelAPIView tests
# ==============================

class TestAdminDebugPanelAPI:
    URL = '/api/debug/panel/'

    def test_unauthenticated(self):
        client = Client()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_non_developer(self, store_v):
        user = User.objects.create_user(
            username="nodev", password="pass123", email="nodev@test.com",
            is_staff=True,
        )
        Staff.objects.create(name="一般", store=store_v, user=user)
        client = Client()
        client.login(username="nodev", password="pass123")
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_developer_access(self, su_api_client, device):
        resp = su_api_client.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert 'devices' in data
        assert 'events' in data


# ==============================
# LogLevelControlAPIView tests
# ==============================

class TestLogLevelControlAPI:
    URL = '/api/debug/log-level/'

    def test_get_unauthenticated(self):
        client = Client()
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_get_level(self, su_api_client):
        resp = su_api_client.get(self.URL)
        assert resp.status_code == 200
        assert 'log_level' in resp.json()

    def test_post_valid_level(self, su_api_client):
        resp = su_api_client.post(
            self.URL,
            {'log_level': 'WARNING'},
            format='json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['log_level'] == 'WARNING'
        assert data['applied'] is True
        assert SystemConfig.get('log_level') == 'WARNING'

    def test_post_invalid_level(self, su_api_client):
        resp = su_api_client.post(
            self.URL,
            {'log_level': 'BOGUS'},
            format='json',
        )
        assert resp.status_code == 400

    def test_post_non_developer(self, store_v):
        user = User.objects.create_user(
            username="nodev2", password="pass123", email="nodev2@test.com",
            is_staff=True,
        )
        Staff.objects.create(name="一般2", store=store_v, user=user)
        client = Client()
        client.login(username="nodev2", password="pass123")
        resp = client.post(
            self.URL,
            json.dumps({'log_level': 'DEBUG'}),
            content_type='application/json',
        )
        assert resp.status_code == 403


# ==============================
# IoTDeviceDebugView tests
# ==============================

class TestIoTDeviceDebugView:

    def test_unauthenticated(self, device):
        client = Client()
        resp = client.get(f'/admin/debug/device/{device.id}/')
        # Redirect to login
        assert resp.status_code == 302

    def test_developer_access(self, su_client, device):
        IoTEvent.objects.create(
            device=device, event_type="sensor", mq9_value=300.0,
        )
        resp = su_client.get(f'/admin/debug/device/{device.id}/')
        assert resp.status_code == 200

    def test_non_developer_forbidden(self, store_v, device):
        user = User.objects.create_user(
            username="nodev3", password="pass123", email="nodev3@test.com",
            is_staff=True,
        )
        Staff.objects.create(name="一般3", store=store_v, user=user)
        client = Client()
        client.login(username="nodev3", password="pass123")
        resp = client.get(f'/admin/debug/device/{device.id}/')
        assert resp.status_code == 403
