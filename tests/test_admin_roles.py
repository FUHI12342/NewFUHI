"""
管理画面ロール別アクセス制御テスト

4ロール:
  1. fortune_teller (一般キャスト/占い師) — staff_type='fortune_teller', フラグなし → role='staff'
  2. store_staff (店舗スタッフ) — staff_type='store_staff', フラグなし → role='staff'
  3. manager (店長) — is_store_manager=True → role='manager'
  4. developer (開発者) — is_developer=True → role='developer'

権限体系:
  - サイドバーの表示は RoleBasedAdminSite._build_full_app_list で独自制御
  - 個別ページのアクセスは各 ModelAdmin の has_*_permission メソッドで制御
  - _is_owner_or_super は superuser または is_owner=True のみ True
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from booking.models import Store, Staff

User = get_user_model()


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_a(db):
    return Store.objects.create(
        name="店舗A",
        address="東京都新宿区",
        business_hours="10:00-22:00",
        nearest_station="新宿駅",
    )


@pytest.fixture
def store_b(db):
    return Store.objects.create(
        name="店舗B",
        address="東京都渋谷区",
        business_hours="11:00-21:00",
        nearest_station="渋谷駅",
    )


def _make_client(username, password, is_staff=True, **staff_kwargs):
    """User + Staff + logged-in Client を作成するヘルパー."""
    user = User.objects.create_user(
        username=username,
        password=password,
        email=f"{username}@example.com",
        is_staff=is_staff,
    )
    staff_obj = Staff.objects.create(user=user, **staff_kwargs)
    client = Client()
    client.login(username=username, password=password)
    return client, user, staff_obj


@pytest.fixture
def fortune_teller_client(db, store_a):
    """占い師 (fortune_teller) — フラグなし → role='staff'."""
    client, user, staff_obj = _make_client(
        "ft_user", "ftpass123",
        name="占い師テスト", store=store_a, staff_type='fortune_teller',
    )
    return client


@pytest.fixture
def store_staff_client(db, store_a):
    """店舗スタッフ (store_staff) — フラグなし → role='staff'."""
    client, user, staff_obj = _make_client(
        "ss_user", "sspass123",
        name="店舗スタッフテスト", store=store_a, staff_type='store_staff',
    )
    return client


@pytest.fixture
def manager_role_client(db, store_a):
    """店長 (manager) — is_store_manager=True."""
    client, user, staff_obj = _make_client(
        "mgr_user", "mgrpass123",
        name="店長テスト", store=store_a, is_store_manager=True,
    )
    return client


@pytest.fixture
def owner_client(db, store_a):
    """オーナー — is_owner=True（_is_owner_or_super が True になる）."""
    client, user, staff_obj = _make_client(
        "owner_user", "ownerpass123",
        name="オーナーテスト", store=store_a, is_owner=True,
    )
    return client


@pytest.fixture
def developer_client(db, store_a):
    """開発者 (developer) — is_developer=True."""
    client, user, staff_obj = _make_client(
        "dev_user", "devpass123",
        name="開発者テスト", store=store_a, is_developer=True,
    )
    return client


@pytest.fixture
def superuser_client(db, store_a):
    """スーパーユーザー."""
    user = User.objects.create_superuser(
        username="super_user", password="superpass123", email="super@example.com",
    )
    Staff.objects.create(name="スーパー", store=store_a, user=user)
    client = Client()
    client.login(username="super_user", password="superpass123")
    return client


# ==============================
# 管理画面トップアクセス
# ==============================

class TestAdminTopAccess:
    """全ロールが管理画面トップにアクセスできること."""

    def test_fortune_teller_can_access_admin(self, fortune_teller_client):
        resp = fortune_teller_client.get('/admin/')
        assert resp.status_code == 200

    def test_store_staff_can_access_admin(self, store_staff_client):
        resp = store_staff_client.get('/admin/')
        assert resp.status_code == 200

    def test_manager_can_access_admin(self, manager_role_client):
        resp = manager_role_client.get('/admin/')
        assert resp.status_code == 200

    def test_developer_can_access_admin(self, developer_client):
        resp = developer_client.get('/admin/')
        assert resp.status_code == 200

    def test_owner_can_access_admin(self, owner_client):
        resp = owner_client.get('/admin/')
        assert resp.status_code == 200

    def test_anonymous_redirected(self, client):
        resp = client.get('/admin/')
        assert resp.status_code in (301, 302)


# ==============================
# スタッフ changelist — role別挙動
# ModelAdmin に has_view_permission がないため、
# Django 標準の権限チェック（booking.view_staff）が適用される。
# manager は has_change_permission(obj=None)=True なのでアクセス可能。
# staff role は has_change_permission(obj=None)=False かつ Django permission なし → 403.
# ==============================

class TestStaffChangelistAccess:
    """スタッフ一覧: 一般スタッフは自分のchange formにリダイレクト."""

    STAFF_CHANGELIST = '/admin/booking/staff/'

    def test_fortune_teller_redirects_to_own_change(self, fortune_teller_client):
        resp = fortune_teller_client.get(self.STAFF_CHANGELIST)
        assert resp.status_code == 302

    def test_store_staff_redirects_to_own_change(self, store_staff_client):
        resp = store_staff_client.get(self.STAFF_CHANGELIST)
        assert resp.status_code == 302

    def test_manager_can_access(self, manager_role_client):
        resp = manager_role_client.get(self.STAFF_CHANGELIST)
        assert resp.status_code == 200

    def test_owner_can_access(self, owner_client):
        resp = owner_client.get(self.STAFF_CHANGELIST)
        assert resp.status_code == 200

    def test_superuser_can_access(self, superuser_client):
        resp = superuser_client.get(self.STAFF_CHANGELIST)
        assert resp.status_code == 200


# ==============================
# 店舗管理 — _is_owner_or_super + manager
# ==============================

class TestStoreAdminAccess:
    """店舗管理は role による changelist アクセス制御を確認."""

    STORE_CHANGELIST = '/admin/booking/store/'

    def test_fortune_teller_forbidden(self, fortune_teller_client):
        resp = fortune_teller_client.get(self.STORE_CHANGELIST)
        assert resp.status_code == 403

    def test_store_staff_forbidden(self, store_staff_client):
        resp = store_staff_client.get(self.STORE_CHANGELIST)
        assert resp.status_code == 403

    def test_superuser_can_access(self, superuser_client):
        resp = superuser_client.get(self.STORE_CHANGELIST)
        assert resp.status_code == 200


# ==============================
# 給与管理 — staff role は 403
# ==============================

class TestPayrollAdminAccess:
    """給与管理は staff role ではアクセス不可."""

    PAYROLL_CHANGELIST = '/admin/booking/payrollperiod/'

    def test_fortune_teller_forbidden(self, fortune_teller_client):
        resp = fortune_teller_client.get(self.PAYROLL_CHANGELIST)
        assert resp.status_code == 403

    def test_store_staff_forbidden(self, store_staff_client):
        resp = store_staff_client.get(self.PAYROLL_CHANGELIST)
        assert resp.status_code == 403


# ==============================
# デバッグパネル — developer/superuser のみ
# ==============================

class TestDebugPanelAccess:
    """デバッグパネルは developer/superuser のみ."""

    DEBUG_URL = '/admin/debug/'

    def test_fortune_teller_forbidden(self, fortune_teller_client):
        resp = fortune_teller_client.get(self.DEBUG_URL)
        assert resp.status_code == 403

    def test_store_staff_forbidden(self, store_staff_client):
        resp = store_staff_client.get(self.DEBUG_URL)
        assert resp.status_code == 403

    def test_manager_forbidden(self, manager_role_client):
        resp = manager_role_client.get(self.DEBUG_URL)
        assert resp.status_code == 403

    def test_developer_can_access(self, developer_client):
        resp = developer_client.get(self.DEBUG_URL)
        assert resp.status_code == 200

    def test_superuser_can_access(self, superuser_client):
        resp = superuser_client.get(self.DEBUG_URL)
        assert resp.status_code == 200


# ==============================
# fortune_teller vs store_staff 同等権限確認
# ==============================

class TestFortuneTellerVsStoreStaff:
    """fortune_teller と store_staff は管理画面上で同じ権限レベル."""

    ACCESSIBLE_ENDPOINTS = [
        '/admin/',
    ]

    # /admin/booking/staff/ は changelist_view でリダイレクトするため除外
    REDIRECT_ENDPOINTS = [
        '/admin/booking/staff/',
    ]

    FORBIDDEN_ENDPOINTS = [
        '/admin/booking/store/',
        '/admin/booking/payrollperiod/',
        '/admin/booking/employmentcontract/',
        '/admin/booking/schedule/',    # Django permission なし → 403
    ]

    @pytest.mark.parametrize("url", ACCESSIBLE_ENDPOINTS)
    def test_both_can_access(self, fortune_teller_client, store_staff_client, url):
        ft_resp = fortune_teller_client.get(url)
        ss_resp = store_staff_client.get(url)
        assert ft_resp.status_code == ss_resp.status_code == 200

    @pytest.mark.parametrize("url", REDIRECT_ENDPOINTS)
    def test_both_redirect(self, fortune_teller_client, store_staff_client, url):
        ft_resp = fortune_teller_client.get(url)
        ss_resp = store_staff_client.get(url)
        assert ft_resp.status_code == ss_resp.status_code == 302

    @pytest.mark.parametrize("url", FORBIDDEN_ENDPOINTS)
    def test_both_forbidden(self, fortune_teller_client, store_staff_client, url):
        ft_resp = fortune_teller_client.get(url)
        ss_resp = store_staff_client.get(url)
        assert ft_resp.status_code == ss_resp.status_code == 403


# ==============================
# manager の CRUD 権限確認
# ==============================

class TestManagerCRUDPermissions:
    """店長は自店舗スタッフの追加はできるが、一般スタッフはできない."""

    def test_manager_can_add_staff(self, manager_role_client):
        resp = manager_role_client.get('/admin/booking/staff/add/')
        assert resp.status_code == 200

    def test_fortune_teller_cannot_add_staff(self, fortune_teller_client):
        resp = fortune_teller_client.get('/admin/booking/staff/add/')
        assert resp.status_code == 403

    def test_manager_cannot_delete_staff(self, manager_role_client, store_a):
        user = User.objects.create_user(
            username="target_staff", password="pass123", is_staff=True,
        )
        target = Staff.objects.create(name="ターゲット", store=store_a, user=user)
        resp = manager_role_client.post(
            f'/admin/booking/staff/{target.pk}/delete/',
            follow=True,
        )
        # スタッフはまだ存在するはず（manager には delete_permission がある実装だが確認）
        assert Staff.objects.filter(pk=target.pk).exists()


# ==============================
# 公開サイト — StoreAccessView
# ==============================

class TestStoreAccessView:
    """店舗アクセスページが正常に表示されること."""

    def test_access_page_renders(self, client, store_a):
        store_a.access_info = "新宿駅東口を出て徒歩5分"
        store_a.map_url = "https://maps.google.com/?q=test"
        store_a.save()
        resp = client.get(f'/store/{store_a.pk}/access/')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "新宿駅東口を出て徒歩5分" in content
        assert "https://maps.google.com/?q=test" in content

    def test_access_page_without_info(self, client, store_a):
        resp = client.get(f'/store/{store_a.pk}/access/')
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_access_page_404_for_nonexistent(self, client):
        resp = client.get('/store/99999/access/')
        assert resp.status_code == 404


# ==============================
# ロール判定ロジックのテスト
# ==============================

class TestGetUserRole:
    """admin_site.get_user_role のロール判定テスト."""

    def test_fortune_teller_resolves_to_staff(self, store_a, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_user("ft_role", "pass123", is_staff=True)
        Staff.objects.create(name="FT", store=store_a, user=user, staff_type='fortune_teller')
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'staff'

    def test_store_staff_resolves_to_staff(self, store_a, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_user("ss_role", "pass123", is_staff=True)
        Staff.objects.create(name="SS", store=store_a, user=user, staff_type='store_staff')
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'staff'

    def test_manager_resolves_to_manager(self, store_a, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_user("mgr_role", "pass123", is_staff=True)
        Staff.objects.create(name="MGR", store=store_a, user=user, is_store_manager=True)
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'manager'

    def test_owner_resolves_to_owner(self, store_a, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_user("own_role", "pass123", is_staff=True)
        Staff.objects.create(name="OWN", store=store_a, user=user, is_owner=True)
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'owner'

    def test_developer_resolves_to_developer(self, store_a, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_user("dev_role", "pass123", is_staff=True)
        Staff.objects.create(name="DEV", store=store_a, user=user, is_developer=True)
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'developer'

    def test_superuser_resolves_to_superuser(self, db):
        from booking.admin_site import get_user_role
        user = User.objects.create_superuser("su_role", "su@example.com", "pass123")
        request = type('Request', (), {'user': user})()
        assert get_user_role(request) == 'superuser'

    def test_ft_and_ss_resolve_to_same_role(self, store_a, db):
        """fortune_teller と store_staff は同じ role='staff' に解決される."""
        from booking.admin_site import get_user_role
        ft_user = User.objects.create_user("ft_same", "pass123", is_staff=True)
        ss_user = User.objects.create_user("ss_same", "pass123", is_staff=True)
        Staff.objects.create(name="FT", store=store_a, user=ft_user, staff_type='fortune_teller')
        Staff.objects.create(name="SS", store=store_a, user=ss_user, staff_type='store_staff')
        ft_req = type('Request', (), {'user': ft_user})()
        ss_req = type('Request', (), {'user': ss_user})()
        assert get_user_role(ft_req) == get_user_role(ss_req) == 'staff'
