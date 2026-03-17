"""勤務実績ダッシュボード テスト"""
import json
import pytest
from datetime import date
from django.test import Client


@pytest.mark.django_db
class TestStaffPerformanceDashboardView:
    def test_returns_200(self, admin_client):
        resp = admin_client.get('/admin/attendance/performance/')
        assert resp.status_code == 200

    def test_contains_title(self, admin_client):
        resp = admin_client.get('/admin/attendance/performance/')
        assert '勤務実績' in resp.content.decode()

    def test_requires_auth(self):
        client = Client()
        resp = client.get('/admin/attendance/performance/')
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestAttendancePerformanceAPI:
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/attendance/performance/')
        assert resp.status_code in (302, 403)

    def test_returns_200(self, admin_client):
        resp = admin_client.get('/api/attendance/performance/')
        assert resp.status_code == 200

    def test_response_structure(self, admin_client):
        resp = admin_client.get('/api/attendance/performance/')
        data = json.loads(resp.content)
        assert 'year' in data
        assert 'month' in data
        assert 'rows' in data
        assert isinstance(data['rows'], list)

    def test_default_year_month(self, admin_client):
        today = date.today()
        resp = admin_client.get('/api/attendance/performance/')
        data = json.loads(resp.content)
        assert data['year'] == today.year
        assert data['month'] == today.month

    def test_with_attendance_data(self, admin_client, work_attendance):
        resp = admin_client.get(
            f'/api/attendance/performance/'
            f'?year={work_attendance.date.year}&month={work_attendance.date.month}'
        )
        data = json.loads(resp.content)
        staff_ids = [r['staff_id'] for r in data['rows']]
        assert work_attendance.staff_id in staff_ids

    def test_row_fields(self, admin_client, work_attendance):
        resp = admin_client.get(
            f'/api/attendance/performance/'
            f'?year={work_attendance.date.year}&month={work_attendance.date.month}'
        )
        data = json.loads(resp.content)
        row = next(r for r in data['rows'] if r['staff_id'] == work_attendance.staff_id)
        for key in ('staff_name', 'store_name', 'attendance_days', 'total_minutes',
                    'regular_minutes', 'overtime_minutes', 'late_night_minutes',
                    'holiday_minutes', 'break_minutes'):
            assert key in row

    def test_aggregation_correct(self, admin_client, work_attendance):
        resp = admin_client.get(
            f'/api/attendance/performance/'
            f'?year={work_attendance.date.year}&month={work_attendance.date.month}'
            f'&staff_id={work_attendance.staff_id}'
        )
        data = json.loads(resp.content)
        assert len(data['rows']) == 1
        row = data['rows'][0]
        assert row['regular_minutes'] == 420
        assert row['overtime_minutes'] == 60
        assert row['total_minutes'] == 480
        assert row['attendance_days'] == 1

    def test_invalid_month_400(self, admin_client):
        resp = admin_client.get('/api/attendance/performance/?month=13')
        assert resp.status_code == 400

    def test_invalid_year_400(self, admin_client):
        resp = admin_client.get('/api/attendance/performance/?year=abc')
        assert resp.status_code == 400

    def test_store_filter(self, admin_client, store, work_attendance):
        resp = admin_client.get(
            f'/api/attendance/performance/?store_id={store.id}'
            f'&year={work_attendance.date.year}&month={work_attendance.date.month}'
        )
        data = json.loads(resp.content)
        for row in data['rows']:
            assert row['store_name'] == store.name

    def test_empty_month_returns_zero(self, admin_client, staff):
        resp = admin_client.get('/api/attendance/performance/?year=2020&month=1')
        data = json.loads(resp.content)
        for row in data['rows']:
            assert row['attendance_days'] == 0


@pytest.mark.django_db
class TestAttendanceSummaryService:
    def test_returns_list(self, store, staff):
        from booking.services.attendance_summary import get_monthly_summary
        result = get_monthly_summary(store=store, year=2025, month=4)
        assert isinstance(result, list)

    def test_zero_when_no_data(self, store, staff):
        from booking.services.attendance_summary import get_monthly_summary
        result = get_monthly_summary(store=store, year=2020, month=1)
        assert all(r['attendance_days'] == 0 for r in result)

    def test_correct_aggregation(self, store, staff, work_attendance):
        from booking.services.attendance_summary import get_monthly_summary
        result = get_monthly_summary(
            store=store, year=work_attendance.date.year, month=work_attendance.date.month,
        )
        row = next(r for r in result if r['staff_id'] == staff.id)
        assert row['attendance_days'] == 1
        assert row['regular_minutes'] == 420
        assert row['total_minutes'] == 480

    def test_staff_id_filter(self, store, staff, work_attendance):
        from booking.services.attendance_summary import get_monthly_summary
        result = get_monthly_summary(
            store=store, year=work_attendance.date.year,
            month=work_attendance.date.month, staff_id=staff.id,
        )
        assert len(result) == 1
        assert result[0]['staff_id'] == staff.id

    def test_none_store_returns_all(self, store, staff, work_attendance):
        from booking.services.attendance_summary import get_monthly_summary
        result = get_monthly_summary(
            store=None, year=work_attendance.date.year, month=work_attendance.date.month,
        )
        assert any(r['staff_id'] == staff.id for r in result)
