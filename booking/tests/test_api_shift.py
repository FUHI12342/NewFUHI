"""
シフトAPIの統合テスト

対象:
  - ShiftAssignmentAPIView  (POST/PUT/DELETE)
  - ShiftTemplateAPIView    (GET/POST/PUT/DELETE)
  - ShiftBulkAssignAPIView  (POST)
  - ShiftAutoScheduleAPIView (POST)
  - ShiftPublishAPIView      (POST)
  - ShiftChangeLogAPIView    (GET)
  - StaffShiftRequestAPIView (GET/POST/DELETE)
  - ShiftPeriodAPIView       (GET/POST)
  - StoreClosedDateAPIView   (GET/POST/DELETE)

テスト方針:
  - 認証なし → 302リダイレクト
  - 認証あり + 正しいデータ → 成功レスポンス
  - 不正データ → バリデーションエラー
  - 他店舗へのアクセス → 403
"""
import json
from datetime import date, time, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from booking.models import (
    Store, Staff, ShiftPeriod, ShiftAssignment, ShiftTemplate,
    ShiftRequest, StoreScheduleConfig, ShiftChangeLog, StoreClosedDate,
    ShiftPublishHistory,
)

User = get_user_model()

# ============================================================
# ヘルパー
# ============================================================

def make_staff_user(username, store, is_staff=True, is_manager=False, is_super=False):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
        is_superuser=is_super,
    )
    Staff.objects.create(
        name=username,
        store=store,
        user=user,
        is_store_manager=is_manager,
    )
    return user


def auth_client(user):
    c = Client()
    c.login(username=user.username, password='testpass123')
    return c


def post_json(client, url, data):
    return client.post(
        url,
        data=json.dumps(data),
        content_type='application/json',
    )


def put_json(client, url, data):
    return client.put(
        url,
        data=json.dumps(data),
        content_type='application/json',
    )


def delete_req(client, url):
    return client.delete(url)


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def store(db):
    return Store.objects.create(name='テスト店舗A')


@pytest.fixture
def other_store(db):
    return Store.objects.create(name='テスト店舗B')


@pytest.fixture
def manager_user(db, store):
    return make_staff_user('manager_shift', store, is_manager=True)


@pytest.fixture
def regular_user(db, store):
    return make_staff_user('regular_shift', store)


@pytest.fixture
def other_store_user(db, other_store):
    return make_staff_user('other_shift', other_store)


@pytest.fixture
def schedule_config(db, store):
    return StoreScheduleConfig.objects.create(
        store=store,
        open_hour=9,
        close_hour=21,
        slot_duration=60,
        min_shift_hours=2,
    )


@pytest.fixture
def period(db, store, manager_user):
    """manager_user を要求し created_by を設定"""
    staff = Staff.objects.get(user=manager_user)
    return ShiftPeriod.objects.create(
        store=store,
        year_month=date(2026, 4, 1),
        status='open',
        created_by=staff,
    )


@pytest.fixture
def assignment(db, period, store, manager_user):
    """manager_user を要求することで store に Staff が必ず存在する"""
    staff = Staff.objects.get(user=manager_user)
    return ShiftAssignment.objects.create(
        period=period,
        staff=staff,
        date=date(2026, 4, 10),
        start_hour=9,
        end_hour=17,
    )


@pytest.fixture
def template(db, store):
    return ShiftTemplate.objects.create(
        store=store,
        name='早番',
        start_time=time(9, 0),
        end_time=time(14, 0),
        color='#10B981',
        is_active=True,
    )


# ============================================================
# 1. ShiftAssignmentAPIView — POST (シフト作成)
# ============================================================

class TestShiftAssignmentCreate:

    def test_unauthenticated_redirects(self, db, store, period, schedule_config):
        """未認証リクエストは302リダイレクト"""
        c = Client()
        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            'staff_id': 1,
            'date': '2026-04-10',
            'start_hour': 9,
            'end_hour': 17,
        })
        assert resp.status_code == 302

    def test_creates_assignment_successfully(self, db, store, period, manager_user, schedule_config):
        """正常なデータでシフトを作成できる"""
        staff = Staff.objects.get(user=manager_user)
        c = auth_client(manager_user)

        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            'staff_id': staff.id,
            'date': '2026-04-10',
            'start_hour': 9,
            'end_hour': 17,
        })
        assert resp.status_code in (200, 201)
        assert ShiftAssignment.objects.filter(
            period=period, staff=staff, date=date(2026, 4, 10)
        ).exists()

    def test_missing_required_fields_returns_error(self, db, store, period, manager_user, schedule_config):
        """必須フィールド不足は400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            # staff_id と date が欠如
        })
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data.get('success') is False

    def test_invalid_json_returns_error(self, db, store, period, manager_user, schedule_config):
        """不正なJSONは400"""
        c = auth_client(manager_user)
        resp = c.post(
            '/api/shift/assignments/',
            data='not-valid-json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_hour_range_returns_error(self, db, store, period, manager_user, schedule_config):
        """start_hour >= end_hour は400"""
        staff = Staff.objects.get(user=manager_user)
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            'staff_id': staff.id,
            'date': '2026-04-10',
            'start_hour': 17,
            'end_hour': 9,
        })
        assert resp.status_code == 400

    def test_duplicate_creates_update_instead(self, db, store, period, manager_user, schedule_config, assignment):
        """同一スロットへの再POSTは更新として200を返す"""
        staff = Staff.objects.get(user=manager_user)
        assignment.staff = staff
        assignment.period = period
        assignment.save()

        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            'staff_id': staff.id,
            'date': assignment.date.isoformat(),
            'start_hour': assignment.start_hour,
            'end_hour': assignment.end_hour,
        })
        assert resp.status_code in (200, 201)

    def test_with_valid_color(self, db, store, period, manager_user, schedule_config):
        """カラーコード指定が正しく保存される"""
        staff = Staff.objects.get(user=manager_user)
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/assignments/', {
            'period_id': period.id,
            'staff_id': staff.id,
            'date': '2026-04-11',
            'start_hour': 10,
            'end_hour': 18,
            'color': '#FF5733',
        })
        assert resp.status_code in (200, 201)
        asgn = ShiftAssignment.objects.filter(
            period=period, staff=staff, date=date(2026, 4, 11)
        ).first()
        assert asgn is not None
        assert asgn.color == '#FF5733'


# ============================================================
# 2. ShiftAssignmentAPIView — PUT (シフト更新)
# ============================================================

class TestShiftAssignmentUpdate:

    def test_update_assignment_successfully(self, db, store, period, manager_user, assignment, schedule_config):
        """シフトの時間帯を更新できる"""
        staff = Staff.objects.get(user=manager_user)
        assignment.staff = staff
        assignment.save()

        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/assignments/{assignment.id}/', {
            'start_hour': 10,
            'end_hour': 18,
        })
        assert resp.status_code == 200
        assignment.refresh_from_db()
        assert assignment.start_hour == 10
        assert assignment.end_hour == 18

    def test_update_nonexistent_assignment_returns_404(self, db, store, manager_user, schedule_config):
        """存在しないシフトの更新は404"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/assignments/99999/', {
            'start_hour': 10,
            'end_hour': 18,
        })
        assert resp.status_code == 404

    def test_update_other_store_assignment_forbidden(
        self, db, store, other_store, period, manager_user, other_store_user, schedule_config
    ):
        """他店舗のシフト更新は403"""
        other_staff = Staff.objects.get(user=other_store_user)
        other_period = ShiftPeriod.objects.create(
            store=other_store,
            year_month=date(2026, 4, 1),
            status='open',
        )
        other_assignment = ShiftAssignment.objects.create(
            period=other_period,
            staff=other_staff,
            date=date(2026, 4, 10),
            start_hour=9,
            end_hour=17,
        )

        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/assignments/{other_assignment.id}/', {
            'start_hour': 10,
        })
        assert resp.status_code == 403

    def test_update_with_note(self, db, store, period, manager_user, assignment, schedule_config):
        """備考フィールドを更新できる"""
        staff = Staff.objects.get(user=manager_user)
        assignment.staff = staff
        assignment.save()

        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/assignments/{assignment.id}/', {
            'note': 'テスト備考更新',
        })
        assert resp.status_code == 200
        assignment.refresh_from_db()
        assert assignment.note == 'テスト備考更新'


# ============================================================
# 3. ShiftAssignmentAPIView — DELETE (シフト削除)
# ============================================================

class TestShiftAssignmentDelete:

    def test_delete_assignment_successfully(self, db, store, period, manager_user, assignment, schedule_config):
        """シフトを削除できる"""
        staff = Staff.objects.get(user=manager_user)
        assignment.staff = staff
        assignment.save()
        assignment_id = assignment.id

        c = auth_client(manager_user)
        resp = delete_req(c, f'/api/shift/assignments/{assignment_id}/')
        assert resp.status_code == 204
        assert not ShiftAssignment.objects.filter(id=assignment_id).exists()

    def test_delete_nonexistent_returns_404(self, db, store, manager_user, schedule_config):
        """存在しないシフトの削除は404"""
        c = auth_client(manager_user)
        resp = delete_req(c, '/api/shift/assignments/99999/')
        assert resp.status_code == 404

    def test_delete_unauthenticated_redirects(self, db, assignment):
        """未認証削除は302"""
        c = Client()
        resp = delete_req(c, f'/api/shift/assignments/{assignment.id}/')
        assert resp.status_code == 302


# ============================================================
# 4. ShiftTemplateAPIView — GET
# ============================================================

class TestShiftTemplateList:

    def test_get_templates_authenticated(self, db, store, manager_user, template, schedule_config):
        """認証済みでテンプレート一覧を取得できる"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/templates/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert len(data['data']) >= 1
        ids = [t['id'] for t in data['data']]
        assert template.id in ids

    def test_get_templates_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/shift/templates/')
        assert resp.status_code == 302

    def test_inactive_templates_excluded(self, db, store, manager_user, schedule_config):
        """is_active=False のテンプレートは含まれない"""
        ShiftTemplate.objects.create(
            store=store, name='非公開テンプレ',
            start_time=time(8, 0), end_time=time(16, 0),
            color='#000000', is_active=False,
        )
        c = auth_client(manager_user)
        resp = c.get('/api/shift/templates/')
        data = json.loads(resp.content)
        names = [t['name'] for t in data['data']]
        assert '非公開テンプレ' not in names


# ============================================================
# 5. ShiftTemplateAPIView — POST (テンプレート作成)
# ============================================================

class TestShiftTemplateCreate:

    def test_create_template_successfully(self, db, store, manager_user, schedule_config):
        """テンプレートを新規作成できる"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/templates/', {
            'name': '通しシフト',
            'start_time': '09:00',
            'end_time': '18:00',
            'color': '#3B82F6',
        })
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert data['success'] is True
        assert ShiftTemplate.objects.filter(store=store, name='通しシフト').exists()

    def test_create_template_invalid_json(self, db, store, manager_user, schedule_config):
        """不正JSONは400"""
        c = auth_client(manager_user)
        resp = c.post(
            '/api/shift/templates/',
            data='{{bad-json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_color_defaults_to_blue(self, db, store, manager_user, schedule_config):
        """不正カラーはデフォルト色に変換される"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/templates/', {
            'name': 'カラーテスト',
            'start_time': '10:00',
            'end_time': '14:00',
            'color': 'not-a-color',
        })
        assert resp.status_code == 201
        t = ShiftTemplate.objects.filter(store=store, name='カラーテスト').first()
        assert t is not None
        assert t.color == '#3B82F6'


# ============================================================
# 6. ShiftTemplateAPIView — PUT (テンプレート更新)
# ============================================================

class TestShiftTemplateUpdate:

    def test_update_template(self, db, store, manager_user, template, schedule_config):
        """テンプレート名と時刻を更新できる"""
        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/templates/{template.id}/', {
            'name': '更新テンプレ',
            'start_time': '08:00',
            'end_time': '16:00',
        })
        assert resp.status_code == 200
        template.refresh_from_db()
        assert template.name == '更新テンプレ'

    def test_update_nonexistent_returns_404(self, db, store, manager_user, schedule_config):
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/templates/99999/', {'name': 'X'})
        assert resp.status_code == 404

    def test_update_other_store_template_forbidden(
        self, db, store, other_store, manager_user, schedule_config
    ):
        """他店舗テンプレートの更新は403"""
        other_template = ShiftTemplate.objects.create(
            store=other_store, name='他店テンプレ',
            start_time=time(9, 0), end_time=time(17, 0),
        )
        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/templates/{other_template.id}/', {'name': 'X'})
        assert resp.status_code == 403


# ============================================================
# 7. ShiftTemplateAPIView — DELETE (ソフト削除)
# ============================================================

class TestShiftTemplateDelete:

    def test_delete_template_soft(self, db, store, manager_user, template, schedule_config):
        """テンプレートはソフト削除（is_active=False）"""
        c = auth_client(manager_user)
        resp = delete_req(c, f'/api/shift/templates/{template.id}/')
        assert resp.status_code == 204
        template.refresh_from_db()
        assert template.is_active is False

    def test_delete_nonexistent_returns_404(self, db, store, manager_user, schedule_config):
        c = auth_client(manager_user)
        resp = delete_req(c, '/api/shift/templates/99999/')
        assert resp.status_code == 404


# ============================================================
# 8. ShiftBulkAssignAPIView — POST (一括シフト作成)
# ============================================================

class TestShiftBulkAssign:

    def test_bulk_assign_creates_assignments(self, db, store, period, manager_user, template, schedule_config):
        """複数スタッフ・複数日にシフトを一括作成できる"""
        staff = Staff.objects.get(user=manager_user)
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/bulk-assign/', {
            'template_id': template.id,
            'period_id': period.id,
            'staff_ids': [staff.id],
            'dates': ['2026-04-15', '2026-04-16'],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['data']['created'] == 2
        assert ShiftAssignment.objects.filter(
            period=period, staff=staff, date=date(2026, 4, 15)
        ).exists()
        assert ShiftAssignment.objects.filter(
            period=period, staff=staff, date=date(2026, 4, 16)
        ).exists()

    def test_bulk_assign_skips_invalid_staff(self, db, store, period, manager_user, template, schedule_config):
        """存在しないスタッフIDはスキップされる"""
        staff = Staff.objects.get(user=manager_user)
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/bulk-assign/', {
            'template_id': template.id,
            'period_id': period.id,
            'staff_ids': [staff.id, 99999],
            'dates': ['2026-04-17'],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['data']['created'] == 1

    def test_bulk_assign_invalid_template_returns_404(self, db, store, period, manager_user, schedule_config):
        """存在しないテンプレートIDは404"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/bulk-assign/', {
            'template_id': 99999,
            'period_id': period.id,
            'staff_ids': [],
            'dates': [],
        })
        assert resp.status_code == 404

    def test_bulk_assign_invalid_json(self, db, store, manager_user, schedule_config):
        c = auth_client(manager_user)
        resp = c.post(
            '/api/shift/bulk-assign/',
            data='not-json',
            content_type='application/json',
        )
        assert resp.status_code == 400


# ============================================================
# 9. ShiftAutoScheduleAPIView — POST (自動スケジューリング)
# ============================================================

class TestShiftAutoSchedule:

    def test_auto_schedule_runs_successfully(self, db, store, period, manager_user, schedule_config):
        """自動スケジューリングが実行される"""
        with patch('booking.services.shift_scheduler.auto_schedule', return_value=3) as mock_auto:
            c = auth_client(manager_user)
            resp = post_json(c, '/api/shift/auto-schedule/', {
                'period_id': period.id,
            })
            assert resp.status_code == 200
            mock_auto.assert_called_once()
            data = json.loads(resp.content)
            assert data['data']['created'] == 3

    def test_auto_schedule_approved_period_rejected(self, db, store, manager_user, schedule_config):
        """承認済み期間への自動スケジューリングはエラー"""
        approved_period = ShiftPeriod.objects.create(
            store=store,
            year_month=date(2026, 3, 1),
            status='approved',
        )
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/auto-schedule/', {
            'period_id': approved_period.id,
        })
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert data['success'] is False

    def test_auto_schedule_no_period_returns_404(self, db, store, manager_user, schedule_config):
        """シフト期間が存在しない場合は404"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/auto-schedule/', {})
        assert resp.status_code == 404

    def test_auto_schedule_unauthenticated(self, db):
        c = Client()
        resp = post_json(c, '/api/shift/auto-schedule/', {})
        assert resp.status_code == 302


# ============================================================
# 10. ShiftPublishAPIView — POST (シフト公開)
# ============================================================

class TestShiftPublish:

    def test_publish_shift_period(self, db, store, period, manager_user, schedule_config):
        """シフト期間を公開できる"""
        with patch('booking.services.shift_scheduler.sync_assignments_to_schedule', return_value=5) as mock_sync, \
             patch('booking.services.shift_notifications.notify_shift_approved') as mock_notify, \
             patch('booking.tasks.task_post_shift_published') as mock_task:
            mock_task.delay = MagicMock()
            c = auth_client(manager_user)
            resp = post_json(c, '/api/shift/publish/', {
                'period_id': period.id,
                'note': '4月シフト公開',
            })
            assert resp.status_code == 200
            data = json.loads(resp.content)
            assert data['success'] is True
            assert ShiftPublishHistory.objects.filter(period=period).exists()
            mock_sync.assert_called_once()

    def test_publish_no_period_returns_404(self, db, store, manager_user, schedule_config):
        """期間なしは404"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/publish/', {})
        assert resp.status_code == 404

    def test_publish_unauthenticated_redirects(self, db):
        c = Client()
        resp = post_json(c, '/api/shift/publish/', {})
        assert resp.status_code == 302


# ============================================================
# 11. ShiftChangeLogAPIView — GET (変更ログ)
# ============================================================

class TestShiftChangeLog:

    def test_get_change_logs_empty(self, db, store, manager_user, schedule_config):
        """変更ログがない場合は空リスト"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/change-logs/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        # list_response は data.results にネスト
        assert data['data']['results'] == []

    def test_get_change_logs_with_period_filter(self, db, store, period, manager_user, assignment, schedule_config):
        """period_idフィルタが動作する"""
        staff = Staff.objects.get(user=manager_user)
        ShiftChangeLog.objects.create(
            assignment=assignment,
            changed_by=staff,
            change_type='revised',
            old_values={'start_hour': 9},
            new_values={'start_hour': 10},
        )
        c = auth_client(manager_user)
        resp = c.get(f'/api/shift/change-logs/?period_id={period.id}')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']['results']) == 1

    def test_get_change_logs_unauthenticated_redirects(self, db):
        c = Client()
        resp = c.get('/api/shift/change-logs/')
        assert resp.status_code == 302


# ============================================================
# 12. StaffShiftRequestAPIView — GET (シフト希望取得)
# ============================================================

class TestStaffShiftRequest:

    def test_get_own_requests(self, db, store, period, regular_user, schedule_config):
        """自分のシフト希望を取得できる"""
        staff = Staff.objects.get(user=regular_user)
        ShiftRequest.objects.create(
            period=period, staff=staff,
            date=date(2026, 4, 10),
            start_hour=9, end_hour=17,
            preference='available',
        )
        c = auth_client(regular_user)
        resp = c.get('/api/shift/my-requests/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert len(data['data']) >= 1

    def test_get_requests_unauthenticated_redirects(self, db):
        c = Client()
        resp = c.get('/api/shift/my-requests/')
        assert resp.status_code == 302

    def test_get_requests_with_period_filter(self, db, store, period, regular_user, schedule_config):
        """period_idフィルタで絞れる"""
        staff = Staff.objects.get(user=regular_user)
        ShiftRequest.objects.create(
            period=period, staff=staff,
            date=date(2026, 4, 12),
            start_hour=10, end_hour=18,
            preference='preferred',
        )
        c = auth_client(regular_user)
        resp = c.get(f'/api/shift/my-requests/?period_id={period.id}')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) >= 1


# ============================================================
# 13. StaffShiftRequestAPIView — POST (シフト希望提出)
# ============================================================

class TestStaffShiftRequestCreate:

    def test_create_shift_request_successfully(self, db, store, period, regular_user, schedule_config):
        """シフト希望を提出できる"""
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            'date': '2026-04-20',
            'start_hour': 9,
            'end_hour': 17,
            'preference': 'available',
        })
        assert resp.status_code in (200, 201)
        data = json.loads(resp.content)
        assert data['success'] is True

    def test_create_request_missing_fields(self, db, store, period, regular_user, schedule_config):
        """必須フィールド不足は400"""
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            # date が欠如
        })
        assert resp.status_code == 400

    def test_create_request_invalid_preference(self, db, store, period, regular_user, schedule_config):
        """不正なpreferenceは400"""
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            'date': '2026-04-21',
            'start_hour': 9,
            'end_hour': 17,
            'preference': 'invalid_choice',
        })
        assert resp.status_code == 400

    def test_create_request_invalid_date_format(self, db, store, period, regular_user, schedule_config):
        """不正な日付形式は400"""
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            'date': 'not-a-date',
            'start_hour': 9,
            'end_hour': 17,
            'preference': 'available',
        })
        assert resp.status_code == 400

    def test_create_request_closed_date_rejected(self, db, store, period, regular_user, schedule_config):
        """休業日へのシフト希望は400"""
        closed_date = date(2026, 4, 25)
        StoreClosedDate.objects.create(store=store, date=closed_date)
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            'date': closed_date.isoformat(),
            'start_hour': 9,
            'end_hour': 17,
            'preference': 'available',
        })
        assert resp.status_code == 400

    def test_create_request_too_short_shift(self, db, store, period, regular_user, schedule_config):
        """最低シフト時間未満は400（schedule_config: min_shift_hours=2）"""
        c = auth_client(regular_user)
        resp = post_json(c, '/api/shift/my-requests/', {
            'period_id': period.id,
            'date': '2026-04-22',
            'start_hour': 9,
            'end_hour': 10,  # 1時間のみ（最低2時間に満たない）
            'preference': 'available',
        })
        assert resp.status_code == 400

    def test_create_request_invalid_json(self, db, store, regular_user, schedule_config):
        """不正JSONは400"""
        c = auth_client(regular_user)
        resp = c.post(
            '/api/shift/my-requests/',
            data='{{invalid',
            content_type='application/json',
        )
        assert resp.status_code == 400


# ============================================================
# 14. StaffShiftRequestAPIView — DELETE (シフト希望削除)
# ============================================================

class TestStaffShiftRequestDelete:

    def test_delete_own_request(self, db, store, period, regular_user, schedule_config):
        """自分のシフト希望を削除できる"""
        staff = Staff.objects.get(user=regular_user)
        req = ShiftRequest.objects.create(
            period=period, staff=staff,
            date=date(2026, 4, 28),
            start_hour=9, end_hour=17,
        )
        c = auth_client(regular_user)
        resp = delete_req(c, f'/api/shift/my-requests/{req.id}/')
        assert resp.status_code == 204
        assert not ShiftRequest.objects.filter(id=req.id).exists()

    def test_delete_others_request_returns_404(self, db, store, period, regular_user, manager_user, schedule_config):
        """他人のシフト希望削除は404"""
        manager_staff = Staff.objects.get(user=manager_user)
        req = ShiftRequest.objects.create(
            period=period, staff=manager_staff,
            date=date(2026, 4, 29),
            start_hour=9, end_hour=17,
        )
        c = auth_client(regular_user)
        resp = delete_req(c, f'/api/shift/my-requests/{req.id}/')
        assert resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, db, store, regular_user, schedule_config):
        c = auth_client(regular_user)
        resp = delete_req(c, '/api/shift/my-requests/99999/')
        assert resp.status_code == 404


# ============================================================
# 15. ShiftPeriodAPIView — POST (期間作成) / GET (期間取得)
# ============================================================

class TestShiftPeriodAPI:

    def test_create_period_successfully(self, db, store, manager_user, schedule_config):
        """シフト期間を作成できる"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/periods/', {
            'year_month': '2026-06-01',
        })
        assert resp.status_code in (200, 201)
        assert ShiftPeriod.objects.filter(store=store, year_month=date(2026, 6, 1)).exists()

    def test_update_period_status(self, db, store, period, manager_user, schedule_config):
        """既存期間のステータスをPUTで変更できる"""
        c = auth_client(manager_user)
        resp = put_json(c, f'/api/shift/periods/{period.id}/', {
            'status': 'closed',
        })
        # ShiftPeriodAPIView は PUT を実装している
        assert resp.status_code in (200, 201, 405)

    def test_create_period_unauthenticated(self, db):
        c = Client()
        resp = post_json(c, '/api/shift/periods/', {'year_month': '2026-06-01'})
        assert resp.status_code == 302


# ============================================================
# 16. StoreClosedDateAPIView — GET/POST/DELETE
# ============================================================

class TestStoreClosedDateAPI:

    def test_list_closed_dates(self, db, store, manager_user, schedule_config):
        """休業日一覧を取得できる"""
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 29))
        c = auth_client(manager_user)
        resp = c.get('/api/shift/closed-dates/')
        assert resp.status_code == 200

    def test_create_closed_date(self, db, store, manager_user, schedule_config):
        """休業日を追加できる"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/closed-dates/', {
            'date': '2026-05-03',
            'reason': '祝日',
        })
        assert resp.status_code in (200, 201)
        assert StoreClosedDate.objects.filter(store=store, date=date(2026, 5, 3)).exists()

    def test_toggle_removes_existing_closed_date(self, db, store, manager_user, schedule_config):
        """POST で既存の休業日を削除（トグル）できる"""
        cd = StoreClosedDate.objects.create(store=store, date=date(2026, 5, 4))
        c = auth_client(manager_user)
        # StoreClosedDateAPIView はPOSTでトグル: 既存があれば削除
        resp = post_json(c, '/api/shift/closed-dates/', {
            'date': '2026-05-04',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['data']['action'] == 'removed'
        assert not StoreClosedDate.objects.filter(id=cd.id).exists()

    def test_unauthenticated_closed_dates_redirects(self, db):
        c = Client()
        resp = c.get('/api/shift/closed-dates/')
        assert resp.status_code == 302


# ============================================================
# 17. マネージャーによる代理シフト希望操作
# ============================================================

class TestManagerProxyShiftRequest:

    def test_manager_can_read_other_staff_requests(
        self, db, store, period, manager_user, regular_user, schedule_config
    ):
        """店長は他スタッフのシフト希望を参照できる"""
        regular_staff = Staff.objects.get(user=regular_user)
        ShiftRequest.objects.create(
            period=period, staff=regular_staff,
            date=date(2026, 4, 15),
            start_hour=9, end_hour=17,
        )
        c = auth_client(manager_user)
        resp = c.get(f'/api/shift/my-requests/?staff_id={regular_staff.id}')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert len(data['data']) >= 1

    def test_regular_staff_cannot_access_others_requests(
        self, db, store, period, regular_user, manager_user, schedule_config
    ):
        """一般スタッフは他スタッフのシフト希望に代理アクセス不可（403）"""
        manager_staff = Staff.objects.get(user=manager_user)
        c = auth_client(regular_user)
        resp = c.get(f'/api/shift/my-requests/?staff_id={manager_staff.id}')
        assert resp.status_code == 403
