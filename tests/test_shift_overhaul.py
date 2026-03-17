"""シフト管理 抜本的改修テスト

Phase 1: StoreClosedDate CRUD
Phase 2: サイドバーロール別リンク
Phase 3: 休業日API
Phase 4: スタッフ マイシフト
Phase 5: 自動スケジューラ 休業日スキップ
Phase 6: セキュリティ（認証・IDOR・バリデーション）
"""
import json
import pytest
from datetime import date, time, timedelta

from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from booking.models import (
    Store, Staff, StoreClosedDate, ShiftPeriod, ShiftRequest,
    ShiftAssignment, ShiftTemplate, StoreScheduleConfig,
)

User = get_user_model()


# ==============================
# フィクスチャ
# ==============================

@pytest.fixture
def manager_user(db, store):
    """店長ユーザー（is_staff=True, is_store_manager=True）"""
    user = User.objects.create_user(
        username="mgr_shift", password="mgrpass123",
        email="mgr_shift@test.com", is_staff=True,
    )
    Staff.objects.create(name="テスト店長", store=store, user=user, is_store_manager=True)
    return user


@pytest.fixture
def staff_only_user(db, store):
    """一般スタッフユーザー（is_staff=True, 店長でない）"""
    user = User.objects.create_user(
        username="staff_shift", password="staffpass123",
        email="staff_shift@test.com", is_staff=True,
    )
    Staff.objects.create(name="テスト一般スタッフ", store=store, user=user)
    return user


@pytest.fixture
def mgr_client(manager_user):
    c = Client()
    c.login(username="mgr_shift", password="mgrpass123")
    return c


@pytest.fixture
def staff_client(staff_only_user):
    c = Client()
    c.login(username="staff_shift", password="staffpass123")
    return c


@pytest.fixture
def open_period(db, store, manager_user):
    staff = Staff.objects.get(user=manager_user)
    return ShiftPeriod.objects.create(
        store=store,
        year_month=date(2026, 4, 1),
        deadline=timezone.now() + timedelta(days=14),
        status='open',
        created_by=staff,
    )


@pytest.fixture
def other_store(db):
    """別店舗（IDOR テスト用）"""
    return Store.objects.create(name="別店舗", address="大阪", business_hours="10-20", nearest_station="梅田")


# ==============================
# Phase 1: StoreClosedDate モデル
# ==============================

class TestStoreClosedDate:
    def test_create_closed_date(self, store):
        cd = StoreClosedDate.objects.create(store=store, date=date(2026, 4, 1), reason='元旦')
        assert cd.pk is not None
        assert cd.reason == '元旦'
        assert str(cd) == f"{store.name} 2026-04-01 元旦"

    def test_unique_together(self, store):
        StoreClosedDate.objects.create(store=store, date=date(2026, 5, 1))
        with pytest.raises(Exception):
            StoreClosedDate.objects.create(store=store, date=date(2026, 5, 1))

    def test_different_stores_same_date(self, store, db):
        store2 = Store.objects.create(name="第二店舗", address="大阪", business_hours="10-20", nearest_station="梅田")
        StoreClosedDate.objects.create(store=store, date=date(2026, 5, 1))
        cd2 = StoreClosedDate.objects.create(store=store2, date=date(2026, 5, 1))
        assert cd2.pk is not None


# ==============================
# Phase 2: サイドバーロール別リンク
# ==============================

class TestSidebarRoleLinks:
    def test_manager_sees_shift_calendar(self, mgr_client):
        resp = mgr_client.get('/admin/')
        content = resp.content.decode()
        assert resp.status_code == 200
        assert 'シフトカレンダー' in content

    def test_staff_sees_shift_calendar(self, staff_client):
        resp = staff_client.get('/admin/')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'シフトカレンダー' in content
        assert 'マイシフト' not in content

    def test_sidebar_links_by_role_config(self):
        from booking.admin_site import SIDEBAR_CUSTOM_LINKS_BY_ROLE
        shift_links = SIDEBAR_CUSTOM_LINKS_BY_ROLE['shift']
        assert 'manager' in shift_links
        assert 'staff' in shift_links
        assert len(shift_links['staff']) == 1
        assert 'シフトカレンダー' in str(shift_links['staff'][0]['name'])
        assert len(shift_links['manager']) == 2


# ==============================
# Phase 3: 休業日API
# ==============================

class TestClosedDateAPI:
    def test_get_empty(self, mgr_client):
        resp = mgr_client.get('/api/shift/closed-dates/?year=2026&month=4')
        assert resp.status_code == 200
        assert resp.json() == []

    def test_toggle_add(self, mgr_client, store):
        resp = mgr_client.post(
            '/api/shift/closed-dates/',
            data=json.dumps({'date': '2026-04-10'}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['action'] == 'added'
        assert StoreClosedDate.objects.filter(store=store, date=date(2026, 4, 10)).exists()

    def test_toggle_remove(self, mgr_client, store):
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 10))
        resp = mgr_client.post(
            '/api/shift/closed-dates/',
            data=json.dumps({'date': '2026-04-10'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['action'] == 'removed'
        assert not StoreClosedDate.objects.filter(store=store, date=date(2026, 4, 10)).exists()

    def test_get_with_data(self, mgr_client, store):
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 5), reason='定休日')
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 12))
        resp = mgr_client.get('/api/shift/closed-dates/?year=2026&month=4')
        data = resp.json()
        assert len(data) == 2
        assert data[0]['date'] == '2026-04-05'
        assert data[0]['reason'] == '定休日'

    def test_invalid_date(self, mgr_client):
        resp = mgr_client.post(
            '/api/shift/closed-dates/',
            data=json.dumps({'date': 'invalid'}),
            content_type='application/json',
        )
        assert resp.status_code == 400


# ==============================
# Phase 4: スタッフ マイシフト
# ==============================

class TestStaffMyShift:
    def test_my_shift_redirects_to_calendar(self, staff_client):
        """旧URL /admin/shift/my/ は /admin/shift/calendar/ にリダイレクト"""
        resp = staff_client.get('/admin/shift/my/')
        assert resp.status_code == 301
        assert '/admin/shift/calendar/' in resp.url

    def test_my_shift_redirect_manager(self, mgr_client):
        """店長も旧URLはリダイレクト"""
        resp = mgr_client.get('/admin/shift/my/')
        assert resp.status_code == 301
        assert '/admin/shift/calendar/' in resp.url

    def test_calendar_staff_role_context(self, staff_client):
        """スタッフがシフトカレンダーにアクセス→is_staff_role=True"""
        resp = staff_client.get('/admin/shift/calendar/')
        assert resp.status_code == 200
        assert resp.context['is_staff_role'] is True
        assert resp.context['user_role'] == 'staff'

    def test_calendar_manager_role_context(self, mgr_client):
        """店長がシフトカレンダーにアクセス→is_staff_role=False"""
        resp = mgr_client.get('/admin/shift/calendar/')
        assert resp.status_code == 200
        assert resp.context['is_staff_role'] is False
        assert resp.context['user_role'] == 'manager'

    def test_shift_request_create(self, staff_client, open_period, staff_only_user):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': 10,
                'end_hour': 18,
                'preference': 'preferred',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['preference'] == 'preferred'
        assert data['start_hour'] == 10

    def test_shift_request_list(self, staff_client, open_period, staff_only_user):
        staff = Staff.objects.get(user=staff_only_user)
        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 15), start_hour=10, end_hour=18,
            preference='preferred',
        )
        resp = staff_client.get(f'/api/shift/my-requests/?period_id={open_period.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    def test_shift_request_delete(self, staff_client, open_period, staff_only_user):
        staff = Staff.objects.get(user=staff_only_user)
        req = ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 15), start_hour=10, end_hour=18,
        )
        resp = staff_client.delete(f'/api/shift/my-requests/{req.id}/')
        assert resp.status_code == 204
        assert not ShiftRequest.objects.filter(pk=req.id).exists()

    def test_shift_request_delete_other_user(self, mgr_client, open_period, staff_only_user):
        """他ユーザーの希望は削除不可"""
        staff = Staff.objects.get(user=staff_only_user)
        req = ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 15), start_hour=10, end_hour=18,
        )
        resp = mgr_client.delete(f'/api/shift/my-requests/{req.id}/')
        assert resp.status_code == 404

    def test_shift_request_invalid_preference(self, staff_client, open_period):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': 10,
                'end_hour': 18,
                'preference': 'invalid',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_no_staff_403(self, db):
        user = User.objects.create_user(
            username="nostaff", password="nopass123", is_staff=True,
        )
        c = Client()
        c.login(username="nostaff", password="nopass123")
        resp = c.get('/api/shift/my-requests/')
        assert resp.status_code == 403


# ==============================
# Phase 5: 自動スケジューラ 休業日スキップ
# ==============================

class TestAutoScheduleClosedDates:
    def test_skips_closed_dates(self, store, open_period, staff_only_user, store_schedule_config):
        staff = Staff.objects.get(user=staff_only_user)
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 10))

        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 10), start_hour=10, end_hour=18,
            preference='preferred',
        )
        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 11), start_hour=10, end_hour=18,
            preference='preferred',
        )

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(open_period)

        assert count == 1
        assert not ShiftAssignment.objects.filter(date=date(2026, 4, 10)).exists()
        assert ShiftAssignment.objects.filter(date=date(2026, 4, 11)).exists()

    def test_no_closed_dates_normal(self, store, open_period, staff_only_user, store_schedule_config):
        staff = Staff.objects.get(user=staff_only_user)
        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 10), start_hour=10, end_hour=18,
            preference='preferred',
        )
        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(open_period)
        assert count == 1

    def test_preferred_before_available(self, store, open_period, staff_only_user, store_schedule_config):
        """preferred が available より先に処理されることを確認"""
        staff = Staff.objects.get(user=staff_only_user)
        # available を先に作成
        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 10), start_hour=10, end_hour=18,
            preference='available',
        )
        ShiftRequest.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 11), start_hour=10, end_hour=18,
            preference='preferred',
        )

        from booking.services.shift_scheduler import auto_schedule
        count = auto_schedule(open_period)
        assert count == 2


# ==============================
# Phase 6: セキュリティ
# ==============================

class TestAPIAuthentication:
    """未認証ユーザーが API にアクセスできないことを確認"""

    def test_unauthenticated_closed_dates_get(self, db):
        c = Client()
        resp = c.get('/api/shift/closed-dates/?year=2026&month=4')
        assert resp.status_code == 302  # リダイレクト→ログイン

    def test_unauthenticated_closed_dates_post(self, db):
        c = Client()
        resp = c.post(
            '/api/shift/closed-dates/',
            data=json.dumps({'date': '2026-04-10'}),
            content_type='application/json',
        )
        assert resp.status_code == 302

    def test_unauthenticated_my_requests(self, db):
        c = Client()
        resp = c.get('/api/shift/my-requests/')
        assert resp.status_code == 302

    def test_unauthenticated_assignments(self, db):
        c = Client()
        resp = c.post(
            '/api/shift/assignments/',
            data=json.dumps({'period_id': 1, 'staff_id': 1, 'date': '2026-04-10'}),
            content_type='application/json',
        )
        assert resp.status_code == 302

    def test_unauthenticated_templates(self, db):
        c = Client()
        resp = c.get('/api/shift/templates/')
        assert resp.status_code == 302

    def test_unauthenticated_auto_schedule(self, db):
        c = Client()
        resp = c.post('/api/shift/auto-schedule/', content_type='application/json')
        assert resp.status_code == 302

    def test_unauthenticated_publish(self, db):
        c = Client()
        resp = c.post('/api/shift/publish/', content_type='application/json')
        assert resp.status_code == 302

    def test_unauthenticated_periods(self, db):
        c = Client()
        resp = c.post(
            '/api/shift/periods/',
            data=json.dumps({'year_month': '2026-04-01'}),
            content_type='application/json',
        )
        assert resp.status_code == 302

    def test_unauthenticated_my_shift_redirect(self, db):
        """旧URL: 未認証でも301リダイレクト"""
        c = Client()
        resp = c.get('/admin/shift/my/')
        assert resp.status_code == 301


class TestIDORProtection:
    """他店舗のリソースにアクセスできないことを確認"""

    def test_assignment_put_other_store(self, mgr_client, store, other_store, open_period):
        """他店舗のアサインメントは更新不可"""
        other_period = ShiftPeriod.objects.create(
            store=other_store, year_month=date(2026, 4, 1), status='open',
        )
        other_user = User.objects.create_user(username="other1", password="pass123", is_staff=True)
        other_staff = Staff.objects.create(name="別店舗スタッフ", store=other_store, user=other_user)
        assignment = ShiftAssignment.objects.create(
            period=other_period, staff=other_staff,
            date=date(2026, 4, 10), start_hour=10, end_hour=18,
        )
        resp = mgr_client.put(
            f'/api/shift/assignments/{assignment.id}/',
            data=json.dumps({'start_hour': 11}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_assignment_delete_other_store(self, mgr_client, store, other_store, open_period):
        """他店舗のアサインメントは削除不可"""
        other_period = ShiftPeriod.objects.create(
            store=other_store, year_month=date(2026, 5, 1), status='open',
        )
        other_user = User.objects.create_user(username="other2", password="pass123", is_staff=True)
        other_staff = Staff.objects.create(name="別店舗スタッフ2", store=other_store, user=other_user)
        assignment = ShiftAssignment.objects.create(
            period=other_period, staff=other_staff,
            date=date(2026, 4, 10), start_hour=10, end_hour=18,
        )
        resp = mgr_client.delete(
            f'/api/shift/assignments/{assignment.id}/',
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_template_put_other_store(self, mgr_client, store, other_store):
        """他店舗のテンプレートは更新不可"""
        template = ShiftTemplate.objects.create(
            store=other_store, name="他店テンプレ",
            start_time=time(9, 0), end_time=time(17, 0),
        )
        resp = mgr_client.put(
            f'/api/shift/templates/{template.id}/',
            data=json.dumps({'name': 'hacked'}),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_period_put_other_store(self, mgr_client, store, other_store):
        """他店舗の期間は更新不可"""
        other_period = ShiftPeriod.objects.create(
            store=other_store, year_month=date(2026, 5, 1), status='open',
        )
        resp = mgr_client.put(
            f'/api/shift/periods/{other_period.id}/',
            data=json.dumps({'status': 'closed'}),
            content_type='application/json',
        )
        assert resp.status_code == 404  # get_object_or_404 with store filter


class TestHourValidation:
    """start_hour/end_hour の範囲バリデーション"""

    def test_invalid_start_hour_negative(self, staff_client, open_period):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': -1,
                'end_hour': 18,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_end_hour_over_24(self, staff_client, open_period):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': 10,
                'end_hour': 25,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_start_after_end(self, staff_client, open_period):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': 18,
                'end_hour': 10,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_start_equals_end(self, staff_client, open_period):
        resp = staff_client.post(
            '/api/shift/my-requests/',
            data=json.dumps({
                'period_id': open_period.id,
                'date': '2026-04-15',
                'start_hour': 10,
                'end_hour': 10,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400


class TestGetUserStoreFallback:
    """_get_user_store のフォールバック動作テスト"""

    def test_no_staff_returns_none(self, db):
        """Staff に紐付かないユーザーは None を返す"""
        user = User.objects.create_user(
            username="nostaffuser", password="pass123", is_staff=True,
        )
        c = Client()
        c.login(username="nostaffuser", password="pass123")
        # API は store=None で 403 を返すはず
        resp = c.post(
            '/api/shift/closed-dates/',
            data=json.dumps({'date': '2026-04-10'}),
            content_type='application/json',
        )
        assert resp.status_code == 403
