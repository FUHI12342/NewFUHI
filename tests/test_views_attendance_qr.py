"""勤怠テスト"""
import json
import pytest
from datetime import date
from django.test import Client
from booking.models import AttendanceStamp, AttendanceTOTPConfig, WorkAttendance


@pytest.mark.django_db
class TestAttendanceQRDisplay:
    def test_qr_page_returns_200(self, admin_client):
        resp = admin_client.get('/admin/attendance/qr/')
        assert resp.status_code == 200

    def test_board_returns_200(self, admin_client):
        resp = admin_client.get('/admin/attendance/board/')
        assert resp.status_code == 200

    def test_qr_requires_auth(self):
        client = Client()
        resp = client.get('/admin/attendance/qr/')
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestAttendanceStampAPI:
    def test_clock_in(self, admin_client, staff, store):
        resp = admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['staff_name'] == staff.name

    def test_clock_out(self, admin_client, staff):
        resp = admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_out'}),
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_duplicate_stamp_rejected(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        resp = admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '5分以内' in json.loads(resp.content)['error']

    def test_missing_staff_id(self, admin_client):
        resp = admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_stamp_creates_attendance(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        attendance = WorkAttendance.objects.filter(staff=staff, date=date.today()).first()
        assert attendance is not None
        assert attendance.source == 'qr'

    def test_invalid_json(self, admin_client):
        resp = admin_client.post(
            '/api/attendance/stamp/',
            'not json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_nonexistent_staff(self, admin_client):
        resp = admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': 99999, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_day_status_api(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        resp = admin_client.get('/api/attendance/day-status/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data) >= 1


@pytest.mark.django_db
class TestAntifraud:
    def test_geo_fence_inside(self):
        from booking.services.totp_service import check_geo_fence
        assert check_geo_fence(35.6812, 139.7671, 35.6815, 139.7675, 200)

    def test_geo_fence_outside(self):
        from booking.services.totp_service import check_geo_fence
        assert not check_geo_fence(35.6812, 139.7671, 36.0, 140.0, 200)

    def test_duplicate_check(self, db, staff):
        AttendanceStamp.objects.create(staff=staff, stamp_type='clock_in')
        from booking.services.totp_service import check_duplicate_stamp
        assert check_duplicate_stamp(staff.id, 'clock_in')

    def test_no_duplicate(self, db, staff):
        from booking.services.totp_service import check_duplicate_stamp
        assert not check_duplicate_stamp(staff.id, 'clock_in')

    def test_ip_recorded(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        stamp = AttendanceStamp.objects.filter(staff=staff).first()
        assert stamp.ip_address is not None


@pytest.fixture
def totp_config(db, store):
    """Create a TOTP config for the store."""
    return AttendanceTOTPConfig.objects.create(
        store=store,
        totp_secret='JBSWY3DPEHPK3PXP',  # test secret
        totp_interval=30,
        is_active=True,
    )


@pytest.fixture
def staff_with_pin(db, staff):
    """Staff with a PIN set."""
    staff.set_attendance_pin('1234')
    staff.save()
    return staff


@pytest.mark.django_db
class TestAttendanceStampPage:
    def test_stamp_page_returns_200(self, store):
        client = Client()
        resp = client.get(f'/attendance/stamp/?store_id={store.id}&code=123456')
        assert resp.status_code == 200
        assert b'attendance_stamp' in resp.content or b'staff-select' in resp.content

    def test_stamp_page_missing_store_id(self):
        client = Client()
        resp = client.get('/attendance/stamp/')
        assert resp.status_code == 400

    def test_stamp_page_invalid_store(self):
        client = Client()
        resp = client.get('/attendance/stamp/?store_id=99999')
        assert resp.status_code == 404

    def test_stamp_page_shows_staffs(self, store, staff):
        client = Client()
        resp = client.get(f'/attendance/stamp/?store_id={store.id}&code=123456')
        assert resp.status_code == 200
        assert staff.name.encode() in resp.content


@pytest.mark.django_db
class TestQRStampAPI:
    def _get_valid_code(self, totp_config):
        from booking.services.totp_service import get_current_totp
        return get_current_totp(totp_config.totp_secret, totp_config.totp_interval)

    def test_qr_stamp_success(self, store, staff_with_pin, totp_config):
        client = Client()
        code = self._get_valid_code(totp_config)
        resp = client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': code,
                'pin': '1234',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['staff_name'] == staff_with_pin.name

    def test_qr_stamp_creates_attendance(self, store, staff_with_pin, totp_config):
        client = Client()
        code = self._get_valid_code(totp_config)
        client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': code,
                'pin': '1234',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        attendance = WorkAttendance.objects.filter(
            staff=staff_with_pin, date=date.today()
        ).first()
        assert attendance is not None
        assert attendance.source == 'qr'

    def test_qr_stamp_invalid_totp(self, store, staff_with_pin, totp_config):
        client = Client()
        resp = client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '000000',
                'pin': '1234',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert '有効期限' in json.loads(resp.content)['error']

    def test_qr_stamp_wrong_pin(self, store, staff_with_pin, totp_config):
        client = Client()
        code = self._get_valid_code(totp_config)
        resp = client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': code,
                'pin': '9999',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'PIN' in json.loads(resp.content)['error']

    def test_qr_stamp_missing_fields(self, store):
        client = Client()
        resp = client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({'store_id': store.id}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_qr_stamp_duplicate_rejected(self, store, staff_with_pin, totp_config):
        client = Client()
        code = self._get_valid_code(totp_config)
        payload = json.dumps({
            'store_id': store.id,
            'staff_id': staff_with_pin.id,
            'totp_code': code,
            'pin': '1234',
            'stamp_type': 'clock_in',
        })
        client.post('/api/attendance/qr-stamp/', payload, content_type='application/json')
        resp = client.post('/api/attendance/qr-stamp/', payload, content_type='application/json')
        assert resp.status_code == 400
        assert '5分以内' in json.loads(resp.content)['error']

    def test_qr_stamp_no_totp_config(self, store, staff_with_pin):
        client = Client()
        resp = client.post(
            '/api/attendance/qr-stamp/',
            json.dumps({
                'store_id': store.id,
                'staff_id': staff_with_pin.id,
                'totp_code': '123456',
                'pin': '1234',
                'stamp_type': 'clock_in',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert 'TOTP' in json.loads(resp.content)['error']


@pytest.mark.django_db
class TestManualStampAPI:
    def test_manual_stamp_success(self, admin_client, staff):
        resp = admin_client.post(
            '/api/attendance/manual-stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert 'operator' in data

    def test_manual_stamp_creates_attendance(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/manual-stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        attendance = WorkAttendance.objects.filter(
            staff=staff, date=date.today()
        ).first()
        assert attendance is not None
        assert attendance.source == 'manual'

    def test_manual_stamp_requires_auth(self):
        client = Client()
        resp = client.post(
            '/api/attendance/manual-stamp/',
            json.dumps({'staff_id': 1, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_manual_stamp_duplicate_rejected(self, admin_client, staff):
        payload = json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'})
        admin_client.post('/api/attendance/manual-stamp/', payload, content_type='application/json')
        resp = admin_client.post('/api/attendance/manual-stamp/', payload, content_type='application/json')
        assert resp.status_code == 400
        assert '5分以内' in json.loads(resp.content)['error']

    def test_manual_stamp_records_operator(self, admin_client, staff):
        admin_client.post(
            '/api/attendance/manual-stamp/',
            json.dumps({'staff_id': staff.id, 'stamp_type': 'clock_in'}),
            content_type='application/json',
        )
        stamp = AttendanceStamp.objects.filter(staff=staff).first()
        assert 'manual:' in stamp.user_agent
