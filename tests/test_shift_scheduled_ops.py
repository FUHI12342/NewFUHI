"""スケジュール済みシフト操作テスト

- スケジュール取消 (scheduled → open, assignments削除)
- 再募集 (scheduled → open, assignments保持)
- スケジュール済み個別編集 (PUT/DELETE)
"""
import json
import pytest
from datetime import date, time, timedelta

from django.test import Client
from django.contrib.auth import get_user_model
from django.utils import timezone

from booking.models import (
    Store, Staff, ShiftPeriod, ShiftRequest,
    ShiftAssignment, ShiftPublishHistory,
)

User = get_user_model()


# ==============================
# フィクスチャ
# ==============================

@pytest.fixture
def store_so(db):
    return Store.objects.create(
        name="スケジュールテスト店舗", address="東京",
        business_hours="10-20", nearest_station="新宿",
    )


@pytest.fixture
def mgr_user_so(db, store_so):
    user = User.objects.create_user(
        username="mgr_so", password="mgrpass123",
        email="mgr_so@test.com", is_staff=True,
    )
    Staff.objects.create(
        name="テスト店長SO", store=store_so, user=user,
        is_store_manager=True,
    )
    return user


@pytest.fixture
def staff_a_so(db, store_so):
    user = User.objects.create_user(
        username="staff_a_so", password="pass123",
        email="staff_a@test.com", is_staff=True,
    )
    return Staff.objects.create(
        name="スタッフA", store=store_so, user=user,
    )


@pytest.fixture
def mgr_client_so(mgr_user_so):
    c = Client()
    c.login(username="mgr_so", password="mgrpass123")
    return c


@pytest.fixture
def scheduled_period(db, store_so, mgr_user_so, staff_a_so):
    """scheduled状態のシフト期間（アサインメント付き）"""
    mgr_staff = Staff.objects.get(user=mgr_user_so)
    period = ShiftPeriod.objects.create(
        store=store_so,
        year_month=date(2026, 6, 1),
        deadline=timezone.now() + timedelta(days=14),
        status='scheduled',
        created_by=mgr_staff,
    )
    ShiftAssignment.objects.create(
        period=period, staff=staff_a_so,
        date=date(2026, 6, 10), start_hour=10, end_hour=18,
        start_time=time(10, 0), end_time=time(18, 0),
    )
    ShiftAssignment.objects.create(
        period=period, staff=staff_a_so,
        date=date(2026, 6, 11), start_hour=9, end_hour=17,
        start_time=time(9, 0), end_time=time(17, 0),
    )
    return period


# ==============================
# スケジュール取消 (scheduled → open)
# ==============================

class TestRevertScheduled:
    def test_revert_deletes_assignments(
        self, mgr_client_so, scheduled_period,
    ):
        """scheduled撤回でアサインメント全削除 + open に戻る"""
        assert ShiftAssignment.objects.filter(
            period=scheduled_period,
        ).count() == 2

        res = mgr_client_so.post(
            '/api/shift/revoke/',
            data=json.dumps({
                'period_id': scheduled_period.id,
                'reason': 'やり直し',
            }),
            content_type='application/json',
        )
        assert res.status_code == 200
        body = res.json()
        data = body['data']
        assert data['status'] == 'open'
        assert data['cancelled'] == 2

        scheduled_period.refresh_from_db()
        assert scheduled_period.status == 'open'
        assert ShiftAssignment.objects.filter(
            period=scheduled_period,
        ).count() == 0

    def test_revert_creates_history(
        self, mgr_client_so, scheduled_period,
    ):
        """撤回履歴が作成される"""
        mgr_client_so.post(
            '/api/shift/revoke/',
            data=json.dumps({
                'period_id': scheduled_period.id,
                'reason': 'テスト取消',
            }),
            content_type='application/json',
        )
        history = ShiftPublishHistory.objects.filter(
            period=scheduled_period, action='revoke',
        ).first()
        assert history is not None
        assert history.reason == 'テスト取消'

    def test_revert_open_period_fails(
        self, mgr_client_so, store_so, mgr_user_so,
    ):
        """open期間に対する撤回は400"""
        mgr_staff = Staff.objects.get(user=mgr_user_so)
        open_period = ShiftPeriod.objects.create(
            store=store_so,
            year_month=date(2026, 7, 1),
            status='open',
            created_by=mgr_staff,
        )
        res = mgr_client_so.post(
            '/api/shift/revoke/',
            data=json.dumps({'period_id': open_period.id}),
            content_type='application/json',
        )
        assert res.status_code == 400


# ==============================
# 再募集 (scheduled → open, assignments保持)
# ==============================

class TestReopenForRecruitment:
    def test_reopen_keeps_assignments(
        self, mgr_client_so, scheduled_period,
    ):
        """再募集でアサインメント保持 + open に戻る"""
        res = mgr_client_so.post(
            '/api/shift/reopen/',
            data=json.dumps({
                'period_id': scheduled_period.id,
            }),
            content_type='application/json',
        )
        assert res.status_code == 200
        body = res.json()
        data = body['data']
        assert data['status'] == 'open'
        assert data['kept_assignments'] == 2

        scheduled_period.refresh_from_db()
        assert scheduled_period.status == 'open'
        assert ShiftAssignment.objects.filter(
            period=scheduled_period,
        ).count() == 2

    def test_reopen_creates_history(
        self, mgr_client_so, scheduled_period,
    ):
        """再募集履歴が作成される"""
        mgr_client_so.post(
            '/api/shift/reopen/',
            data=json.dumps({
                'period_id': scheduled_period.id,
                'reason': '追加募集',
            }),
            content_type='application/json',
        )
        history = ShiftPublishHistory.objects.filter(
            period=scheduled_period, action='reopen',
        ).first()
        assert history is not None
        assert history.reason == '追加募集'

    def test_reopen_non_scheduled_fails(
        self, mgr_client_so, store_so, mgr_user_so,
    ):
        """scheduled以外の期間に対する再募集は400"""
        mgr_staff = Staff.objects.get(user=mgr_user_so)
        open_period = ShiftPeriod.objects.create(
            store=store_so,
            year_month=date(2026, 8, 1),
            status='open',
            created_by=mgr_staff,
        )
        res = mgr_client_so.post(
            '/api/shift/reopen/',
            data=json.dumps({'period_id': open_period.id}),
            content_type='application/json',
        )
        assert res.status_code == 400


# ==============================
# スケジュール済み個別シフト編集
# ==============================

class TestScheduledShiftEdit:
    def test_edit_scheduled_assignment(
        self, mgr_client_so, scheduled_period, staff_a_so,
    ):
        """scheduled状態のシフトを編集できる"""
        assignment = ShiftAssignment.objects.filter(
            period=scheduled_period, staff=staff_a_so,
        ).first()
        res = mgr_client_so.put(
            f'/api/shift/assignments/{assignment.id}/',
            data=json.dumps({
                'start_hour': 11,
                'end_hour': 19,
                'start_time': '11:00',
                'end_time': '19:00',
                'note': '変更テスト',
            }),
            content_type='application/json',
        )
        assert res.status_code == 200
        assignment.refresh_from_db()
        assert assignment.start_hour == 11
        assert assignment.end_hour == 19
        assert assignment.note == '変更テスト'

    def test_delete_scheduled_assignment(
        self, mgr_client_so, scheduled_period, staff_a_so,
    ):
        """scheduled状態のシフトを削除できる"""
        assignment = ShiftAssignment.objects.filter(
            period=scheduled_period, staff=staff_a_so,
        ).first()
        pk = assignment.id
        res = mgr_client_so.delete(
            f'/api/shift/assignments/{pk}/',
        )
        assert res.status_code == 204
        assert not ShiftAssignment.objects.filter(pk=pk).exists()

    def test_create_new_assignment_for_scheduled(
        self, mgr_client_so, scheduled_period, staff_a_so,
    ):
        """scheduled状態の期間にシフトを追加できる"""
        res = mgr_client_so.post(
            '/api/shift/assignments/',
            data=json.dumps({
                'period_id': scheduled_period.id,
                'staff_id': staff_a_so.id,
                'date': '2026-06-15',
                'start_hour': 10,
                'end_hour': 18,
                'start_time': '10:00',
                'end_time': '18:00',
            }),
            content_type='application/json',
        )
        assert res.status_code == 201
        assert ShiftAssignment.objects.filter(
            period=scheduled_period, date=date(2026, 6, 15),
        ).exists()
