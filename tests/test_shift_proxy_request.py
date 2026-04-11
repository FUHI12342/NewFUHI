"""シフト希望 代理登録テスト

manager以上が staff_id パラメータで他スタッフのシフト希望を代理操作できることを検証。
"""
import json
import pytest
from datetime import date, timedelta

from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from booking.models import Store, Staff, ShiftPeriod, ShiftRequest

User = get_user_model()

API_URL = '/api/shift/my-requests/'


# ==============================
# フィクスチャ
# ==============================

@pytest.fixture
def store_px(db):
    return Store.objects.create(
        name="代理テスト店舗", address="東京", business_hours="10-20",
        nearest_station="渋谷",
    )


@pytest.fixture
def other_store_px(db):
    return Store.objects.create(
        name="他店舗", address="大阪", business_hours="10-20",
        nearest_station="梅田",
    )


@pytest.fixture
def manager_user_px(db, store_px):
    user = User.objects.create_user(
        username="mgr_proxy", password="mgrpass123",
        email="mgr_proxy@test.com", is_staff=True,
    )
    Staff.objects.create(
        name="代理テスト店長", store=store_px, user=user,
        is_store_manager=True,
    )
    return user


@pytest.fixture
def staff_user_px(db, store_px):
    user = User.objects.create_user(
        username="staff_proxy", password="staffpass123",
        email="staff_proxy@test.com", is_staff=True,
    )
    Staff.objects.create(name="一般スタッフA", store=store_px, user=user)
    return user


@pytest.fixture
def target_staff_px(db, store_px):
    """代理操作の対象スタッフ"""
    user = User.objects.create_user(
        username="target_proxy", password="targetpass123",
        email="target_proxy@test.com", is_staff=True,
    )
    return Staff.objects.create(name="対象スタッフB", store=store_px, user=user)


@pytest.fixture
def other_store_staff_px(db, other_store_px):
    user = User.objects.create_user(
        username="other_store_proxy", password="otherpass123",
        email="other_store@test.com", is_staff=True,
    )
    return Staff.objects.create(name="他店舗スタッフ", store=other_store_px, user=user)


@pytest.fixture
def open_period_px(db, store_px, manager_user_px):
    staff = Staff.objects.get(user=manager_user_px)
    return ShiftPeriod.objects.create(
        store=store_px,
        year_month=date(2026, 5, 1),
        deadline=timezone.now() + timedelta(days=14),
        status='open',
        created_by=staff,
    )


@pytest.fixture
def mgr_client_px(manager_user_px):
    c = Client()
    c.login(username="mgr_proxy", password="mgrpass123")
    return c


@pytest.fixture
def staff_client_px(staff_user_px):
    c = Client()
    c.login(username="staff_proxy", password="staffpass123")
    return c


# ==============================
# POST: 代理登録
# ==============================

class TestProxyPost:
    def test_manager_can_proxy_create(
        self, mgr_client_px, target_staff_px, open_period_px,
    ):
        """店長が他スタッフの希望を代理登録できる"""
        res = mgr_client_px.post(
            API_URL,
            data=json.dumps({
                'staff_id': target_staff_px.id,
                'period_id': open_period_px.id,
                'date': '2026-05-10',
                'start_hour': 10,
                'end_hour': 18,
                'preference': 'preferred',
            }),
            content_type='application/json',
        )
        assert res.status_code == 201
        req = ShiftRequest.objects.get(staff=target_staff_px)
        assert req.date == date(2026, 5, 10)
        assert req.preference == 'preferred'

    def test_regular_staff_cannot_proxy(
        self, staff_client_px, target_staff_px, open_period_px,
    ):
        """一般スタッフはstaff_id指定で403"""
        res = staff_client_px.post(
            API_URL,
            data=json.dumps({
                'staff_id': target_staff_px.id,
                'period_id': open_period_px.id,
                'date': '2026-05-10',
                'start_hour': 10,
                'end_hour': 18,
            }),
            content_type='application/json',
        )
        assert res.status_code == 403
        assert ShiftRequest.objects.filter(staff=target_staff_px).count() == 0

    def test_cross_store_blocked(
        self, mgr_client_px, other_store_staff_px, open_period_px,
    ):
        """他店舗スタッフへの代理登録は404"""
        res = mgr_client_px.post(
            API_URL,
            data=json.dumps({
                'staff_id': other_store_staff_px.id,
                'period_id': open_period_px.id,
                'date': '2026-05-10',
                'start_hour': 10,
                'end_hour': 18,
            }),
            content_type='application/json',
        )
        assert res.status_code == 404

    def test_without_staff_id_uses_own(
        self, staff_client_px, staff_user_px, open_period_px,
    ):
        """staff_id未指定時は自分の希望を登録"""
        res = staff_client_px.post(
            API_URL,
            data=json.dumps({
                'period_id': open_period_px.id,
                'date': '2026-05-11',
                'start_hour': 9,
                'end_hour': 17,
                'preference': 'available',
            }),
            content_type='application/json',
        )
        assert res.status_code == 201
        own_staff = Staff.objects.get(user=staff_user_px)
        assert ShiftRequest.objects.filter(staff=own_staff).count() == 1


# ==============================
# GET: 代理取得
# ==============================

class TestProxyGet:
    def test_manager_can_get_other_requests(
        self, mgr_client_px, target_staff_px, open_period_px,
    ):
        """店長がstaff_idで他スタッフの希望を取得できる"""
        ShiftRequest.objects.create(
            period=open_period_px, staff=target_staff_px,
            date=date(2026, 5, 12), start_hour=10, end_hour=18,
            preference='preferred',
        )
        res = mgr_client_px.get(
            f'{API_URL}?staff_id={target_staff_px.id}'
            f'&period_id={open_period_px.id}',
        )
        assert res.status_code == 200
        body = res.json()
        data = body['data']
        assert len(data) == 1
        assert data[0]['date'] == '2026-05-12'

    def test_regular_staff_get_denied(
        self, staff_client_px, target_staff_px, open_period_px,
    ):
        """一般スタッフはstaff_id指定GETで403"""
        res = staff_client_px.get(
            f'{API_URL}?staff_id={target_staff_px.id}',
        )
        assert res.status_code == 403


# ==============================
# DELETE: 代理削除
# ==============================

class TestProxyDelete:
    def test_manager_can_delete_proxy(
        self, mgr_client_px, target_staff_px, open_period_px,
    ):
        """店長がstaff_idで他スタッフの希望を削除できる"""
        req = ShiftRequest.objects.create(
            period=open_period_px, staff=target_staff_px,
            date=date(2026, 5, 13), start_hour=10, end_hour=18,
            preference='preferred',
        )
        res = mgr_client_px.delete(
            f'{API_URL}{req.id}/?staff_id={target_staff_px.id}',
        )
        assert res.status_code == 204
        assert not ShiftRequest.objects.filter(pk=req.id).exists()

    def test_regular_staff_delete_denied(
        self, staff_client_px, target_staff_px, open_period_px,
    ):
        """一般スタッフはstaff_id指定DELETEで403"""
        req = ShiftRequest.objects.create(
            period=open_period_px, staff=target_staff_px,
            date=date(2026, 5, 14), start_hour=10, end_hour=18,
            preference='preferred',
        )
        res = staff_client_px.delete(
            f'{API_URL}{req.id}/?staff_id={target_staff_px.id}',
        )
        assert res.status_code == 403
        assert ShiftRequest.objects.filter(pk=req.id).exists()


# ==============================
# superuser テスト
# ==============================

class TestSuperuserProxy:
    def test_superuser_can_proxy(self, db, store_px, target_staff_px, open_period_px):
        """superuserも代理操作可能"""
        su = User.objects.create_superuser(
            username="su_proxy", password="supass123",
            email="su@test.com",
        )
        Staff.objects.create(name="SUスタッフ", store=store_px, user=su)
        c = Client()
        c.login(username="su_proxy", password="supass123")
        res = c.post(
            API_URL,
            data=json.dumps({
                'staff_id': target_staff_px.id,
                'period_id': open_period_px.id,
                'date': '2026-05-15',
                'start_hour': 10,
                'end_hour': 18,
                'preference': 'available',
            }),
            content_type='application/json',
        )
        assert res.status_code == 201
