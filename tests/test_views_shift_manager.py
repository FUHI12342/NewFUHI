"""シフトView/APIテスト"""
import json
import pytest
from datetime import date, time, timedelta
from django.test import Client
from booking.models import ShiftAssignment, ShiftTemplate, ShiftPublishHistory


@pytest.mark.django_db
class TestManagerShiftCalendarView:
    def test_calendar_returns_200(self, admin_client):
        resp = admin_client.get('/admin/shift/calendar/')
        assert resp.status_code == 200

    def test_calendar_contains_title(self, admin_client):
        resp = admin_client.get('/admin/shift/calendar/')
        assert 'シフトカレンダー' in resp.content.decode()

    def test_calendar_requires_auth(self):
        client = Client()
        resp = client.get('/admin/shift/calendar/')
        assert resp.status_code in (302, 403)

    def test_calendar_with_week_param(self, admin_client):
        resp = admin_client.get('/admin/shift/calendar/?week_start=2026-03-09')
        assert resp.status_code == 200


@pytest.mark.django_db
class TestShiftWeekGridView:
    def test_week_grid_returns_html(self, admin_client):
        resp = admin_client.get('/api/shift/week-grid/')
        assert resp.status_code == 200

    def test_week_grid_with_date(self, admin_client):
        resp = admin_client.get('/api/shift/week-grid/?week_start=2026-03-09')
        assert resp.status_code == 200

    def test_week_grid_contains_table(self, admin_client):
        resp = admin_client.get('/api/shift/week-grid/')
        assert b'<table' in resp.content


@pytest.mark.django_db
class TestShiftAssignmentAPI:
    def test_create_assignment(self, admin_client, shift_period, staff):
        resp = admin_client.post(
            '/api/shift/assignments/',
            json.dumps({
                'period_id': shift_period.id,
                'staff_id': staff.id,
                'date': '2026-03-10',
                'start_hour': 9,
                'end_hour': 17,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        assert ShiftAssignment.objects.filter(staff=staff, date='2026-03-10').exists()

    def test_create_with_template(self, admin_client, shift_period, staff, shift_template):
        resp = admin_client.post(
            '/api/shift/assignments/',
            json.dumps({
                'period_id': shift_period.id,
                'staff_id': staff.id,
                'date': '2026-03-11',
                'template_id': shift_template.id,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201

    def test_update_assignment(self, admin_client, shift_assignment):
        resp = admin_client.put(
            f'/api/shift/assignments/{shift_assignment.id}/',
            json.dumps({'color': '#FF0000', 'note': 'Updated'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        shift_assignment.refresh_from_db()
        assert shift_assignment.color == '#FF0000'

    def test_delete_assignment(self, admin_client, shift_assignment):
        pk = shift_assignment.id
        resp = admin_client.delete(f'/api/shift/assignments/{pk}/')
        assert resp.status_code == 204
        assert not ShiftAssignment.objects.filter(pk=pk).exists()

    def test_create_missing_fields(self, admin_client):
        resp = admin_client.post(
            '/api/shift/assignments/',
            json.dumps({}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_create_invalid_json(self, admin_client):
        resp = admin_client.post(
            '/api/shift/assignments/',
            'not json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_update_nonexistent(self, admin_client):
        resp = admin_client.put(
            '/api/shift/assignments/99999/',
            json.dumps({'note': 'x'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_delete_nonexistent(self, admin_client):
        resp = admin_client.delete('/api/shift/assignments/99999/')
        assert resp.status_code == 404


@pytest.mark.django_db
class TestShiftTemplateAPI:
    def test_list_templates(self, admin_client, shift_template):
        resp = admin_client.get('/api/shift/templates/')
        assert resp.status_code == 200
        body = json.loads(resp.content)
        data = body['data']
        assert len(data) >= 1

    def test_create_template(self, admin_client, store):
        resp = admin_client.post(
            '/api/shift/templates/',
            json.dumps({'name': '通し', 'start_time': '09:00', 'end_time': '21:00'}),
            content_type='application/json',
        )
        assert resp.status_code == 201

    def test_update_template(self, admin_client, shift_template):
        resp = admin_client.put(
            f'/api/shift/templates/{shift_template.id}/',
            json.dumps({'name': '早番改'}),
            content_type='application/json',
        )
        assert resp.status_code == 200

    def test_delete_template(self, admin_client, shift_template):
        resp = admin_client.delete(f'/api/shift/templates/{shift_template.id}/')
        assert resp.status_code == 204
        shift_template.refresh_from_db()
        assert not shift_template.is_active


@pytest.mark.django_db
class TestShiftBulkAssign:
    def test_bulk_assign(self, admin_client, shift_period, staff, shift_template):
        resp = admin_client.post(
            '/api/shift/bulk-assign/',
            json.dumps({
                'template_id': shift_template.id,
                'staff_ids': [staff.id],
                'dates': ['2026-03-10', '2026-03-11'],
                'period_id': shift_period.id,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        body = json.loads(resp.content)
        data = body['data']
        assert data['created'] == 2

    def test_bulk_assign_no_duplicates(self, admin_client, shift_period, staff, shift_template):
        # First call
        admin_client.post(
            '/api/shift/bulk-assign/',
            json.dumps({
                'template_id': shift_template.id,
                'staff_ids': [staff.id],
                'dates': ['2026-03-12'],
                'period_id': shift_period.id,
            }),
            content_type='application/json',
        )
        # Second call - same data
        resp = admin_client.post(
            '/api/shift/bulk-assign/',
            json.dumps({
                'template_id': shift_template.id,
                'staff_ids': [staff.id],
                'dates': ['2026-03-12'],
                'period_id': shift_period.id,
            }),
            content_type='application/json',
        )
        body = json.loads(resp.content)
        data = body['data']
        assert data['created'] == 0


@pytest.mark.django_db
class TestShiftAutoScheduleAPI:
    def test_auto_schedule(self, admin_client, shift_period, shift_request, store_schedule_config):
        resp = admin_client.post(
            '/api/shift/auto-schedule/',
            json.dumps({'period_id': shift_period.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        body = json.loads(resp.content)
        data = body['data']
        assert data['created'] >= 0

    def test_auto_schedule_no_period(self, admin_client):
        resp = admin_client.post(
            '/api/shift/auto-schedule/',
            json.dumps({'period_id': 99999}),
            content_type='application/json',
        )
        assert resp.status_code == 404


@pytest.mark.django_db
class TestShiftPublishAPI:
    def test_publish(self, admin_client, shift_period, shift_assignment, mock_line_notify):
        resp = admin_client.post(
            '/api/shift/publish/',
            json.dumps({'period_id': shift_period.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert ShiftPublishHistory.objects.filter(period=shift_period).exists()

    def test_publish_creates_history(self, admin_client, shift_period, shift_assignment, mock_line_notify):
        admin_client.post(
            '/api/shift/publish/',
            json.dumps({'period_id': shift_period.id}),
            content_type='application/json',
        )
        history = ShiftPublishHistory.objects.filter(period=shift_period).first()
        assert history is not None
        assert history.assignment_count > 0

    def test_publish_no_period(self, admin_client):
        resp = admin_client.post(
            '/api/shift/publish/',
            json.dumps({'period_id': 99999}),
            content_type='application/json',
        )
        assert resp.status_code == 404
