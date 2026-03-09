"""勤怠テスト"""
import json
import pytest
from datetime import date
from django.test import Client
from booking.models import AttendanceStamp, WorkAttendance


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
