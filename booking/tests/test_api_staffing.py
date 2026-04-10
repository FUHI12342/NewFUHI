"""
必要人数設定 API の統合テスト

対象:
  - StaffingRequirementAPIView  GET / PUT
  - StaffingOverrideAPIView     GET / POST / DELETE
"""
import json
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from booking.models import (
    Store, Staff,
    ShiftStaffRequirement, ShiftStaffRequirementOverride,
    StoreScheduleConfig,
)

User = get_user_model()

# ============================================================
# ヘルパー
# ============================================================

def make_staff_user(username, store, is_staff=True, is_manager=False):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
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


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def store(db):
    return Store.objects.create(name='スタッフィングテスト店')


@pytest.fixture
def other_store(db):
    return Store.objects.create(name='他店舗スタッフィング')


@pytest.fixture
def manager_user(db, store):
    return make_staff_user('staffing_manager', store, is_manager=True)


@pytest.fixture
def regular_user(db, store):
    return make_staff_user('staffing_regular', store)


@pytest.fixture
def schedule_config(db, store):
    return StoreScheduleConfig.objects.create(
        store=store, open_hour=9, close_hour=21, slot_duration=60, min_shift_hours=2,
    )


@pytest.fixture
def requirement(db, store):
    return ShiftStaffRequirement.objects.create(
        store=store, day_of_week=0, staff_type='fortune_teller', required_count=3,
    )


@pytest.fixture
def override(db, store):
    return ShiftStaffRequirementOverride.objects.create(
        store=store,
        date=date(2026, 5, 1),
        staff_type='fortune_teller',
        required_count=5,
        reason='GW特別増員',
    )


# ============================================================
# 1. StaffingRequirementAPIView — GET (曜日別必要人数)
# ============================================================

class TestStaffingRequirementGet:

    def test_get_requirements_authenticated(self, db, store, manager_user, requirement, schedule_config):
        """認証済みで曜日別必要人数を取得できる"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert isinstance(data['data'], list)
        ids = [r['id'] for r in data['data']]
        assert requirement.id in ids

    def test_get_requirements_returns_fields(self, db, store, manager_user, requirement, schedule_config):
        """レスポンスに必須フィールドが含まれている"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/')
        data = json.loads(resp.content)
        first = data['data'][0]
        assert 'id' in first
        assert 'day_of_week' in first
        assert 'staff_type' in first
        assert 'required_count' in first

    def test_get_requirements_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/shift/staffing/')
        assert resp.status_code == 302

    def test_get_requirements_empty_store(self, db, store, manager_user, schedule_config):
        """必要人数が未登録の場合は空リスト"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/')
        data = json.loads(resp.content)
        assert data['success'] is True
        # 新しいストアには未登録なので0件
        assert isinstance(data['data'], list)


# ============================================================
# 2. StaffingRequirementAPIView — PUT (一括更新)
# ============================================================

class TestStaffingRequirementPut:

    def test_put_creates_requirement(self, db, store, manager_user, schedule_config):
        """PUTで必要人数を登録できる"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 0, 'staff_type': 'fortune_teller', 'required_count': 4},
                {'day_of_week': 1, 'staff_type': 'store_staff', 'required_count': 2},
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        assert len(data['data']) == 2
        assert ShiftStaffRequirement.objects.filter(
            store=store, day_of_week=0, staff_type='fortune_teller', required_count=4,
        ).exists()

    def test_put_updates_existing_requirement(self, db, store, manager_user, requirement, schedule_config):
        """既存の必要人数を更新できる"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 0, 'staff_type': 'fortune_teller', 'required_count': 10},
            ],
        })
        assert resp.status_code == 200
        requirement.refresh_from_db()
        assert requirement.required_count == 10

    def test_put_invalid_day_of_week_skipped(self, db, store, manager_user, schedule_config):
        """不正な曜日（7以上）はスキップされる"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 7, 'staff_type': 'fortune_teller', 'required_count': 2},
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 0

    def test_put_negative_count_skipped(self, db, store, manager_user, schedule_config):
        """マイナス必要人数はスキップ"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 2, 'staff_type': 'store_staff', 'required_count': -1},
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 0

    def test_put_invalid_staff_type_skipped(self, db, store, manager_user, schedule_config):
        """不正なstaff_typeはスキップ"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 3, 'staff_type': 'invalid_type', 'required_count': 2},
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 0

    def test_put_items_not_list_returns_error(self, db, store, manager_user, schedule_config):
        """itemsがリストでない場合は400"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': 'not-a-list',
        })
        assert resp.status_code == 400

    def test_put_zero_count_accepted(self, db, store, manager_user, schedule_config):
        """required_count=0 は有効（営業なし日など）"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 0, 'staff_type': 'fortune_teller', 'required_count': 0},
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 1

    def test_put_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = put_json(c, '/api/shift/staffing/', {'items': []})
        assert resp.status_code == 302

    def test_put_missing_required_fields_skipped(self, db, store, manager_user, schedule_config):
        """必須フィールドが欠けているアイテムはスキップ"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': 1},  # staff_type と required_count が欠如
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 0

    def test_put_multiple_items_bulk_upsert(self, db, store, manager_user, schedule_config):
        """複数アイテムの一括upsert"""
        c = auth_client(manager_user)
        resp = put_json(c, '/api/shift/staffing/', {
            'items': [
                {'day_of_week': i, 'staff_type': 'fortune_teller', 'required_count': i + 1}
                for i in range(7)
            ],
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['data']) == 7


# ============================================================
# 3. StaffingOverrideAPIView — GET (日付指定オーバーライド一覧)
# ============================================================

class TestStaffingOverrideGet:

    def test_get_overrides_authenticated(self, db, store, manager_user, override, schedule_config):
        """認証済みでオーバーライド一覧を取得できる"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/overrides/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['success'] is True
        ids = [r['id'] for r in data['data']]
        assert override.id in ids

    def test_get_overrides_with_year_month_filter(self, db, store, manager_user, override, schedule_config):
        """year/monthフィルタで月別に絞れる"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/overrides/?year=2026&month=5')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        # 2026-05-01 のオーバーライドが含まれる
        ids = [r['id'] for r in data['data']]
        assert override.id in ids

    def test_get_overrides_filter_excludes_other_months(self, db, store, manager_user, override, schedule_config):
        """別月でフィルタした場合はそのオーバーライドは含まれない"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/overrides/?year=2026&month=6')
        data = json.loads(resp.content)
        ids = [r['id'] for r in data['data']]
        assert override.id not in ids

    def test_get_overrides_returns_correct_fields(self, db, store, manager_user, override, schedule_config):
        """レスポンスに必須フィールドが揃っている"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/overrides/')
        data = json.loads(resp.content)
        first = next((r for r in data['data'] if r['id'] == override.id), None)
        assert first is not None
        assert 'date' in first
        assert 'staff_type' in first
        assert 'required_count' in first
        assert 'reason' in first

    def test_get_overrides_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/shift/staffing/overrides/')
        assert resp.status_code == 302

    def test_get_overrides_invalid_year_month_ignores_filter(self, db, store, manager_user, override, schedule_config):
        """不正なyear/monthは無視される"""
        c = auth_client(manager_user)
        resp = c.get('/api/shift/staffing/overrides/?year=abc&month=xyz')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data['data'], list)


# ============================================================
# 4. StaffingOverrideAPIView — POST (オーバーライド作成)
# ============================================================

class TestStaffingOverridePost:

    def test_create_override_successfully(self, db, store, manager_user, schedule_config):
        """オーバーライドを作成できる"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-01',
            'staff_type': 'fortune_teller',
            'required_count': 6,
            'reason': 'イベント増員',
        })
        assert resp.status_code in (200, 201)
        data = json.loads(resp.content)
        assert data['success'] is True
        assert ShiftStaffRequirementOverride.objects.filter(
            store=store, date=date(2026, 6, 1)
        ).exists()

    def test_create_override_missing_date_returns_error(self, db, store, manager_user, schedule_config):
        """date欠如は400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'staff_type': 'fortune_teller',
            'required_count': 3,
        })
        assert resp.status_code == 400

    def test_create_override_missing_staff_type_returns_error(self, db, store, manager_user, schedule_config):
        """staff_type欠如は400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-02',
            'required_count': 3,
        })
        assert resp.status_code == 400

    def test_create_override_missing_count_returns_error(self, db, store, manager_user, schedule_config):
        """required_count欠如は400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-03',
            'staff_type': 'fortune_teller',
        })
        assert resp.status_code == 400

    def test_create_override_invalid_date_returns_error(self, db, store, manager_user, schedule_config):
        """不正な日付形式は400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': 'not-a-date',
            'staff_type': 'fortune_teller',
            'required_count': 3,
        })
        assert resp.status_code == 400

    def test_create_override_negative_count_returns_error(self, db, store, manager_user, schedule_config):
        """マイナスのrequired_countは400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-04',
            'staff_type': 'fortune_teller',
            'required_count': -1,
        })
        assert resp.status_code == 400

    def test_create_override_invalid_staff_type_returns_error(self, db, store, manager_user, schedule_config):
        """不正なstaff_typeは400"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-05',
            'staff_type': 'invalid_type',
            'required_count': 3,
        })
        assert resp.status_code == 400

    def test_create_override_updates_existing(self, db, store, manager_user, override, schedule_config):
        """同日・同種別の再POSTは更新として200を返す"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': override.date.isoformat(),
            'staff_type': override.staff_type,
            'required_count': 10,
        })
        assert resp.status_code == 200
        override.refresh_from_db()
        assert override.required_count == 10

    def test_create_override_reason_truncated_at_100(self, db, store, manager_user, schedule_config):
        """理由は100文字で切り詰められる"""
        c = auth_client(manager_user)
        long_reason = 'あ' * 200
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-07-01',
            'staff_type': 'store_staff',
            'required_count': 2,
            'reason': long_reason,
        })
        assert resp.status_code in (200, 201)
        obj = ShiftStaffRequirementOverride.objects.get(
            store=store, date=date(2026, 7, 1)
        )
        assert len(obj.reason) <= 100

    def test_create_override_zero_count_accepted(self, db, store, manager_user, schedule_config):
        """required_count=0 は許可（休業日など）"""
        c = auth_client(manager_user)
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-07-02',
            'staff_type': 'fortune_teller',
            'required_count': 0,
        })
        assert resp.status_code in (200, 201)

    def test_create_override_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = post_json(c, '/api/shift/staffing/overrides/', {
            'date': '2026-06-01',
            'staff_type': 'fortune_teller',
            'required_count': 3,
        })
        assert resp.status_code == 302


# ============================================================
# 5. StaffingOverrideAPIView — DELETE (オーバーライド削除)
# ============================================================

class TestStaffingOverrideDelete:

    def test_delete_override_successfully(self, db, store, manager_user, override, schedule_config):
        """オーバーライドを削除できる"""
        override_id = override.id
        c = auth_client(manager_user)
        resp = c.delete(f'/api/shift/staffing/overrides/{override_id}/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['data']['deleted'] == override_id
        assert not ShiftStaffRequirementOverride.objects.filter(id=override_id).exists()

    def test_delete_nonexistent_override_returns_404(self, db, store, manager_user, schedule_config):
        """存在しないIDは404"""
        c = auth_client(manager_user)
        resp = c.delete('/api/shift/staffing/overrides/99999/')
        assert resp.status_code == 404

    def test_delete_other_store_override_returns_404(
        self, db, store, other_store, manager_user, schedule_config
    ):
        """他店舗のオーバーライド削除は404"""
        other_override = ShiftStaffRequirementOverride.objects.create(
            store=other_store,
            date=date(2026, 5, 15),
            staff_type='fortune_teller',
            required_count=2,
        )
        c = auth_client(manager_user)
        resp = c.delete(f'/api/shift/staffing/overrides/{other_override.id}/')
        assert resp.status_code == 404
        # 他店舗のオーバーライドが削除されていないことを確認
        assert ShiftStaffRequirementOverride.objects.filter(id=other_override.id).exists()

    def test_delete_without_pk_returns_400(self, db, store, manager_user, schedule_config):
        """pkなしのDELETEはエラー"""
        c = auth_client(manager_user)
        resp = c.delete('/api/shift/staffing/overrides/')
        # URLがマッチしないので 404、またはpkなしでエラー
        assert resp.status_code in (400, 404, 405)

    def test_delete_unauthenticated_redirects(self, db, override):
        """未認証は302"""
        c = Client()
        resp = c.delete(f'/api/shift/staffing/overrides/{override.id}/')
        assert resp.status_code == 302


# ============================================================
# 6. 店舗なし（Store取得失敗）のフォールバック
# ============================================================

class TestStaffingNoStore:

    def test_get_requirements_returns_403_when_no_store(self, db):
        """店舗が紐づいていないスタッフは403"""
        user = User.objects.create_user(
            username='nostore_user', password='testpass123', is_staff=True
        )
        # Staff を作らない（store なし状態）
        c = Client()
        c.login(username='nostore_user', password='testpass123')
        resp = c.get('/api/shift/staffing/')
        assert resp.status_code == 403

    def test_put_requirements_returns_403_when_no_store(self, db):
        """店舗が紐づいていないスタッフのPUTは403"""
        user = User.objects.create_user(
            username='nostore_put_user', password='testpass123', is_staff=True
        )
        c = Client()
        c.login(username='nostore_put_user', password='testpass123')
        resp = put_json(c, '/api/shift/staffing/', {'items': []})
        assert resp.status_code == 403

    def test_get_overrides_returns_403_when_no_store(self, db):
        """店舗が紐づいていないスタッフはオーバーライド取得も403"""
        user = User.objects.create_user(
            username='nostore_over_user', password='testpass123', is_staff=True
        )
        c = Client()
        c.login(username='nostore_over_user', password='testpass123')
        resp = c.get('/api/shift/staffing/overrides/')
        assert resp.status_code == 403
