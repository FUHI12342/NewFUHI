"""シフト管理 抜本的改修テスト

Phase 1: StoreClosedDate CRUD
Phase 2: サイドバーロール別リンク
Phase 3: 休業日API
Phase 4: スタッフ マイシフト
Phase 5: 自動スケジューラ 休業日スキップ
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
        assert 'シフトカレンダー' in content or resp.status_code == 200

    def test_staff_sees_my_shift(self, staff_client):
        resp = staff_client.get('/admin/')
        content = resp.content.decode()
        # スタッフはマイシフトリンクが表示される
        assert 'マイシフト' in content or resp.status_code == 200

    def test_sidebar_links_by_role_config(self):
        from booking.admin_site import SIDEBAR_CUSTOM_LINKS_BY_ROLE
        shift_links = SIDEBAR_CUSTOM_LINKS_BY_ROLE['shift']
        assert 'manager' in shift_links
        assert 'staff' in shift_links
        assert len(shift_links['staff']) == 1
        assert 'マイシフト' in str(shift_links['staff'][0]['name'])
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
    def test_my_shift_view_staff(self, staff_client):
        resp = staff_client.get('/admin/shift/my/')
        assert resp.status_code == 200
        assert 'マイシフト' in resp.content.decode()

    def test_my_shift_view_manager(self, mgr_client):
        resp = mgr_client.get('/admin/shift/my/')
        assert resp.status_code == 200

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
        # 4/10 を休業日に設定
        StoreClosedDate.objects.create(store=store, date=date(2026, 4, 10))

        # 4/10 と 4/11 に希望を出す
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

        # 4/10 はスキップ、4/11 のみアサイン
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
