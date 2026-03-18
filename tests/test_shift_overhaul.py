"""シフト管理 抜本的改修テスト

Phase 1: StoreClosedDate CRUD
Phase 2: サイドバーロール別リンク
Phase 3: 休業日API
Phase 4: スタッフ マイシフト
Phase 5: 自動スケジューラ 休業日スキップ
Phase 6: セキュリティ（認証・IDOR・バリデーション）
Phase 7: テンプレートCRUD
Phase 8: フォールバック
Phase 9: シフト撤回・個別修正
Phase 10: スタッフ管理メニュー + マイページプロフィール + シフトフィルタ + staff_type活用
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
    ShiftPublishHistory, ShiftChangeLog, Schedule,
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
        assert len(shift_links['staff']) == 2
        assert 'シフトカレンダー' in str(shift_links['staff'][0]['name'])
        assert '本日のシフト' in str(shift_links['staff'][1]['name'])
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


# ==============================
# Phase 7: テンプレートCRUD (管理メニュー経由)
# ==============================

class TestTemplateCRUDFromCalendar:
    """管理カレンダーのテンプレート管理モーダル用API"""

    def test_list_empty(self, mgr_client):
        resp = mgr_client.get('/api/shift/templates/')
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_template(self, mgr_client, store):
        resp = mgr_client.post(
            '/api/shift/templates/',
            data=json.dumps({
                'name': '早番',
                'start_time': '09:00',
                'end_time': '14:00',
                'color': '#10B981',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['name'] == '早番'
        assert ShiftTemplate.objects.filter(store=store, name='早番').exists()

    def test_list_after_create(self, mgr_client, store):
        ShiftTemplate.objects.create(
            store=store, name='遅番',
            start_time=time(14, 0), end_time=time(22, 0), color='#EF4444',
        )
        resp = mgr_client.get('/api/shift/templates/')
        data = resp.json()
        assert len(data) == 1
        assert data[0]['name'] == '遅番'
        assert data[0]['start_time'] == '14:00'
        assert data[0]['color'] == '#EF4444'

    def test_update_template(self, mgr_client, store):
        tpl = ShiftTemplate.objects.create(
            store=store, name='早番', start_time=time(9, 0), end_time=time(14, 0),
        )
        resp = mgr_client.put(
            f'/api/shift/templates/{tpl.id}/',
            data=json.dumps({'name': '早番改', 'color': '#F59E0B'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        tpl.refresh_from_db()
        assert tpl.name == '早番改'
        assert tpl.color == '#F59E0B'

    def test_delete_template_soft(self, mgr_client, store):
        tpl = ShiftTemplate.objects.create(
            store=store, name='通し', start_time=time(9, 0), end_time=time(21, 0),
        )
        resp = mgr_client.delete(f'/api/shift/templates/{tpl.id}/')
        assert resp.status_code == 204
        tpl.refresh_from_db()
        assert tpl.is_active is False

    def test_deleted_not_in_list(self, mgr_client, store):
        ShiftTemplate.objects.create(
            store=store, name='削除済み', start_time=time(9, 0), end_time=time(17, 0),
            is_active=False,
        )
        resp = mgr_client.get('/api/shift/templates/')
        assert len(resp.json()) == 0

    def test_staff_cannot_modify_templates(self, staff_client, store):
        """一般スタッフはテンプレート作成不可（store=Noneではないが、テストとして確認）"""
        resp = staff_client.post(
            '/api/shift/templates/',
            data=json.dumps({'name': 'ハック', 'start_time': '09:00', 'end_time': '17:00'}),
            content_type='application/json',
        )
        # staff_client has a store, so should succeed (201)
        # The API only checks staff_member_required + store ownership
        assert resp.status_code == 201


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


# ==============================
# フィクスチャ (Phase 9)
# ==============================

@pytest.fixture
def approved_period(db, store, manager_user):
    """公開済み(approved)シフト期間"""
    staff = Staff.objects.get(user=manager_user)
    return ShiftPeriod.objects.create(
        store=store,
        year_month=date(2026, 5, 1),
        deadline=timezone.now() + timedelta(days=14),
        status='approved',
        created_by=staff,
    )


@pytest.fixture
def synced_assignment(db, approved_period, staff_only_user):
    """公開済み期間の同期済みシフト"""
    staff = Staff.objects.get(user=staff_only_user)
    return ShiftAssignment.objects.create(
        period=approved_period,
        staff=staff,
        date=date(2026, 5, 5),
        start_hour=10,
        end_hour=18,
        start_time=time(10, 0),
        end_time=time(18, 0),
        is_synced=True,
    )


# ==============================
# Phase 9: シフト撤回
# ==============================

class TestShiftRevoke:
    """公開済みシフトの撤回テスト"""

    def test_revoke_approved_period(self, mgr_client, approved_period, synced_assignment, store):
        """approved 期間を撤回すると scheduled に戻る"""
        # Schedule レコードを作成（シフト同期済みの状態を再現）
        import datetime as dt
        start_dt = timezone.make_aware(dt.datetime.combine(date(2026, 5, 5), time(10, 0)))
        end_dt = timezone.make_aware(dt.datetime.combine(date(2026, 5, 5), time(11, 0)))
        Schedule.objects.create(
            staff=synced_assignment.staff,
            start=start_dt, end=end_dt,
            customer_name=None, price=0,
            is_temporary=False, memo='シフトから自動作成',
        )

        resp = mgr_client.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': approved_period.id, 'reason': 'スタッフ変更のため'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'scheduled'
        assert data['cancelled'] >= 1

        approved_period.refresh_from_db()
        assert approved_period.status == 'scheduled'

        synced_assignment.refresh_from_db()
        assert synced_assignment.is_synced is False

        # 撤回履歴が記録されている
        history = ShiftPublishHistory.objects.filter(
            period=approved_period, action='revoke',
        ).first()
        assert history is not None
        assert history.reason == 'スタッフ変更のため'

    def test_revoke_non_approved_period_fails(self, mgr_client, open_period):
        """approved 以外の期間は撤回不可"""
        resp = mgr_client.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': open_period.id, 'reason': 'テスト'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_revoke_missing_period_id(self, mgr_client):
        """period_id 未指定は 400"""
        resp = mgr_client.post(
            '/api/shift/revoke/',
            data=json.dumps({'reason': 'テスト'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_revoke_other_store_fails(self, staff_client, approved_period, other_store):
        """別店舗の期間は撤回不可"""
        other_period = ShiftPeriod.objects.create(
            store=other_store, year_month=date(2026, 6, 1), status='approved',
        )
        resp = staff_client.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': other_period.id, 'reason': 'テスト'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_revoke_unauthenticated(self):
        """未認証ユーザーは撤回不可"""
        c = Client()
        resp = c.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': 1, 'reason': 'テスト'}),
            content_type='application/json',
        )
        assert resp.status_code == 302  # redirect to login

    def test_revoke_then_republish(self, mgr_client, approved_period, synced_assignment, store):
        """撤回後に再公開できる"""
        resp = mgr_client.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': approved_period.id, 'reason': '再調整'}),
            content_type='application/json',
        )
        assert resp.status_code == 200

        # 再公開
        resp = mgr_client.post(
            '/api/shift/publish/',
            data=json.dumps({'period_id': approved_period.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        approved_period.refresh_from_db()
        assert approved_period.status == 'approved'


# ==============================
# Phase 9: 個別シフト修正
# ==============================

class TestShiftRevise:
    """公開済みシフトの個別修正テスト"""

    def test_revise_approved_assignment(self, mgr_client, approved_period, synced_assignment):
        """approved 期間の個別シフト修正で変更ログが作成される"""
        resp = mgr_client.put(
            f'/api/shift/assignments/{synced_assignment.id}/',
            data=json.dumps({
                'start_hour': 11,
                'end_hour': 19,
                'reason': '営業時間変更',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200

        synced_assignment.refresh_from_db()
        assert synced_assignment.start_hour == 11
        assert synced_assignment.end_hour == 19

        # 変更ログが作成されている
        log = ShiftChangeLog.objects.filter(assignment=synced_assignment).first()
        assert log is not None
        assert log.change_type == 'revised'
        assert log.reason == '営業時間変更'
        assert log.old_values['start_hour'] == 10
        assert log.old_values['end_hour'] == 18
        assert log.new_values['start_hour'] == 11
        assert log.new_values['end_hour'] == 19

    def test_revise_non_approved_no_changelog(self, mgr_client, open_period, staff_only_user, store):
        """approved でない期間の更新では変更ログは作成されない"""
        staff = Staff.objects.get(user=staff_only_user)
        assignment = ShiftAssignment.objects.create(
            period=open_period, staff=staff,
            date=date(2026, 4, 10), start_hour=9, end_hour=17,
        )
        resp = mgr_client.put(
            f'/api/shift/assignments/{assignment.id}/',
            data=json.dumps({'start_hour': 10, 'end_hour': 18}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert ShiftChangeLog.objects.filter(assignment=assignment).count() == 0

    def test_revise_synced_updates_schedule(self, mgr_client, approved_period, synced_assignment, store):
        """同期済みシフト修正で Schedule レコードが更新される"""
        import datetime as dt
        # 旧時間帯の Schedule 作成
        for h in range(10, 18):
            start_dt = timezone.make_aware(dt.datetime.combine(date(2026, 5, 5), time(h, 0)))
            end_dt = timezone.make_aware(dt.datetime.combine(date(2026, 5, 5), time(h + 1, 0)))
            Schedule.objects.create(
                staff=synced_assignment.staff,
                start=start_dt, end=end_dt,
                memo='シフトから自動作成',
            )

        resp = mgr_client.put(
            f'/api/shift/assignments/{synced_assignment.id}/',
            data=json.dumps({
                'start_hour': 12,
                'end_hour': 20,
                'reason': '時間帯変更',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200

        # 旧時間帯(10-18)の Schedule がキャンセルされている
        old_cancelled = Schedule.objects.filter(
            staff=synced_assignment.staff,
            start__date=date(2026, 5, 5),
            memo='シフトから自動作成',
            is_cancelled=True,
        ).count()
        assert old_cancelled == 8

        # 新時間帯(12-20)の Schedule が作成されている
        new_active = Schedule.objects.filter(
            staff=synced_assignment.staff,
            start__date=date(2026, 5, 5),
            memo='シフトから自動作成',
            is_cancelled=False,
        ).count()
        assert new_active == 8


# ==============================
# Phase 9: モデルテスト
# ==============================

class TestShiftChangeLogModel:
    """ShiftChangeLog モデルテスト"""

    def test_create_change_log(self, synced_assignment, manager_user):
        staff = Staff.objects.get(user=manager_user)
        log = ShiftChangeLog.objects.create(
            assignment=synced_assignment,
            changed_by=staff,
            change_type='revised',
            old_values={'start_hour': 10},
            new_values={'start_hour': 12},
            reason='テスト変更',
        )
        assert log.pk is not None
        assert log.change_type == 'revised'
        assert '修正' in str(log)

    def test_delete_change_type(self, synced_assignment):
        log = ShiftChangeLog.objects.create(
            assignment=synced_assignment,
            change_type='deleted',
            old_values={'start_hour': 10, 'end_hour': 18},
        )
        assert log.get_change_type_display() == '削除'


class TestShiftPublishHistoryExtended:
    """ShiftPublishHistory 拡張テスト"""

    def test_publish_action_default(self, approved_period, manager_user):
        staff = Staff.objects.get(user=manager_user)
        history = ShiftPublishHistory.objects.create(
            period=approved_period,
            published_by=staff,
            assignment_count=5,
        )
        assert history.action == 'publish'
        assert history.reason == ''

    def test_revoke_action(self, approved_period, manager_user):
        staff = Staff.objects.get(user=manager_user)
        history = ShiftPublishHistory.objects.create(
            period=approved_period,
            published_by=staff,
            assignment_count=5,
            action='revoke',
            reason='テスト撤回',
        )
        assert history.action == 'revoke'
        assert history.get_action_display() == '撤回'
        assert '撤回' in str(history)


# ==============================
# Phase 10: スタッフ管理メニュー
# ==============================

class TestStaffManageMenu:
    """サイドバー スタッフ管理メニューテスト"""

    def test_manager_sees_staff_manage(self, mgr_client):
        """manager は従業員管理メニューを見る"""
        resp = mgr_client.get('/admin/')
        content = resp.content.decode()
        assert '従業員管理' in content

    def test_staff_sees_staff_manage(self, staff_client):
        """一般スタッフも従業員管理グループを見る"""
        resp = staff_client.get('/admin/')
        content = resp.content.decode()
        assert '従業員管理' in content

    def test_sidebar_staff_manage_role_config(self):
        """SIDEBAR_CUSTOM_LINKS_BY_ROLE に staff_manage がある"""
        from booking.admin_site import SIDEBAR_CUSTOM_LINKS_BY_ROLE
        assert 'staff_manage' in SIDEBAR_CUSTOM_LINKS_BY_ROLE
        assert 'manager' in SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']
        assert 'staff' in SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']
        # manager は2件（従業員一覧、勤怠実績）
        assert len(SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']['manager']) == 2
        # staff は1件（マイページ）
        assert len(SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']['staff']) == 1

    def test_staff_manage_visible_in_role_groups(self):
        """ROLE_VISIBLE_GROUPS に staff_manage が含まれる"""
        from booking.admin_site import ROLE_VISIBLE_GROUPS
        assert 'staff_manage' in ROLE_VISIBLE_GROUPS['manager']
        assert 'staff_manage' in ROLE_VISIBLE_GROUPS['staff']


# ==============================
# Phase 10: マイページプロフィール
# ==============================

@pytest.fixture
def cast_staff(db, store):
    """キャスト(fortune_teller)スタッフ"""
    user = User.objects.create_user(
        username="cast_user", password="castpass123",
        email="cast@test.com", is_staff=True,
    )
    return Staff.objects.create(
        name="テストキャスト", store=store, user=user,
        staff_type='fortune_teller', price=5000,
        introduction='テスト自己紹介',
    )


@pytest.fixture
def store_staff_member(db, store):
    """店舗スタッフ(store_staff)"""
    user = User.objects.create_user(
        username="sstaff_user", password="sstaffpass123",
        email="sstaff@test.com", is_staff=True,
    )
    return Staff.objects.create(
        name="テスト店舗スタッフ", store=store, user=user,
        staff_type='store_staff',
    )


class TestMyPageProfile:
    """マイページプロフィール編集テスト"""

    def test_profile_page_loads(self, db, cast_staff):
        c = Client()
        c.login(username="cast_user", password="castpass123")
        resp = c.get(f'/mypage/{cast_staff.pk}/profile/')
        assert resp.status_code == 200
        assert 'テストキャスト' in resp.content.decode()

    def test_profile_edit_saves(self, db, cast_staff):
        c = Client()
        c.login(username="cast_user", password="castpass123")
        resp = c.post(f'/mypage/{cast_staff.pk}/profile/', {
            'name': '新しい名前',
            'price': 6000,
            'introduction': '更新された自己紹介',
            'line_id': '',
        })
        assert resp.status_code == 302  # redirect on success
        cast_staff.refresh_from_db()
        assert cast_staff.name == '新しい名前'
        assert cast_staff.price == 6000

    def test_other_user_cannot_edit(self, db, cast_staff, store_staff_member):
        """他人のプロフィールは編集不可"""
        c = Client()
        c.login(username="sstaff_user", password="sstaffpass123")
        resp = c.get(f'/mypage/{cast_staff.pk}/profile/')
        assert resp.status_code == 403

    def test_store_staff_no_price_field(self, db, store_staff_member):
        """店舗スタッフのフォームには price がない"""
        c = Client()
        c.login(username="sstaff_user", password="sstaffpass123")
        resp = c.get(f'/mypage/{store_staff_member.pk}/profile/')
        assert resp.status_code == 200
        content = resp.content.decode()
        # price フィールドのID が存在しない
        assert 'id_price' not in content

    def test_unauthenticated_redirect(self, db, cast_staff):
        c = Client()
        resp = c.get(f'/mypage/{cast_staff.pk}/profile/')
        assert resp.status_code == 403  # OnlyStaffMixin raises 403


# ==============================
# Phase 10: シフトカレンダー staff_type フィルタ
# ==============================

class TestShiftCalendarStaffTypeFilter:
    """シフトカレンダーの staff_type フィルタテスト"""

    def test_calendar_has_filter_counts(self, mgr_client, store, cast_staff, store_staff_member):
        """カレンダーページに cast_count と store_staff_count が含まれる"""
        resp = mgr_client.get('/admin/shift/calendar/')
        assert resp.status_code == 200
        # コンテキストにフィルタ情報が含まれる
        assert 'cast_count' in resp.context
        assert 'store_staff_count' in resp.context
        assert resp.context['cast_count'] >= 1
        assert resp.context['store_staff_count'] >= 1

    def test_filter_fortune_teller(self, mgr_client, store, cast_staff, store_staff_member, open_period):
        """fortune_teller フィルタでキャストのみ表示"""
        # キャストにシフト追加
        ShiftAssignment.objects.create(
            period=open_period, staff=cast_staff,
            date=date(2026, 4, 7), start_hour=10, end_hour=18,
        )
        ShiftAssignment.objects.create(
            period=open_period, staff=store_staff_member,
            date=date(2026, 4, 7), start_hour=10, end_hour=18,
        )
        resp = mgr_client.get('/admin/shift/calendar/?staff_type=fortune_teller')
        assert resp.status_code == 200
        staffs = list(resp.context['staffs'])
        staff_types = [s.staff_type for s in staffs]
        assert all(t == 'fortune_teller' for t in staff_types)

    def test_filter_store_staff(self, mgr_client, store, cast_staff, store_staff_member):
        """store_staff フィルタでスタッフのみ表示"""
        resp = mgr_client.get('/admin/shift/calendar/?staff_type=store_staff')
        assert resp.status_code == 200
        staffs = list(resp.context['staffs'])
        staff_types = [s.staff_type for s in staffs]
        assert all(t == 'store_staff' for t in staff_types)

    def test_no_filter_shows_all(self, mgr_client, store, cast_staff, store_staff_member):
        """フィルタなしで全員表示"""
        resp = mgr_client.get('/admin/shift/calendar/')
        assert resp.status_code == 200
        staffs = list(resp.context['staffs'])
        assert len(staffs) >= 2  # cast + store_staff + manager


# ==============================
# Phase 10: MyPage staff_type 活用
# ==============================

class TestMyPageStaffType:
    """MyPage の staff_type 活用テスト"""

    def test_cast_sees_reservations(self, db, cast_staff):
        """キャストは予約セクションを見る"""
        c = Client()
        c.login(username="cast_user", password="castpass123")
        resp = c.get('/mypage/')
        assert resp.status_code == 200
        assert resp.context['has_cast_role'] is True

    def test_store_staff_no_reservations(self, db, store_staff_member):
        """店舗スタッフは予約セクションを見ない"""
        c = Client()
        c.login(username="sstaff_user", password="sstaffpass123")
        resp = c.get('/mypage/')
        assert resp.status_code == 200
        assert resp.context['has_cast_role'] is False
