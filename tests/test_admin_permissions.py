"""
Phase 4: 管理画面権限・ユーティリティのテスト

対象:
  - StaffAdmin: save_model, get_queryset, has_change_permission
  - SiteSettingsAdmin: has_add_permission, has_delete_permission, changelist_view
  - booking/utils.py: get_line_profile
  - booking/line_notify.py: send_line_notify
  - booking/forms.py: StaffForm, AdminMenuConfigForm
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory

from booking.models import Store, Staff, SiteSettings
from booking.admin import StaffAdmin, SiteSettingsAdmin
from booking.utils import get_line_profile
from booking.line_notify import send_line_notify

User = get_user_model()

pytestmark = pytest.mark.django_db


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_a(db):
    return Store.objects.create(
        name="店舗A", address="東京", business_hours="10-22",
        nearest_station="新宿",
    )


@pytest.fixture
def store_b(db):
    return Store.objects.create(
        name="店舗B", address="大阪", business_hours="11-21",
        nearest_station="梅田",
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="su", password="pass123", email="su@test.com",
    )


@pytest.fixture
def owner_user(store_a):
    user = User.objects.create_user(
        username="owner", password="pass123", email="owner@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="オーナー", store=store_a, user=user, is_owner=True)
    return user


@pytest.fixture
def manager_user(store_a):
    user = User.objects.create_user(
        username="mgr", password="pass123", email="mgr@test.com",
        is_staff=True,
    )
    Staff.objects.create(
        name="店長", store=store_a, user=user, is_store_manager=True,
    )
    return user


@pytest.fixture
def regular_staff_user(store_a):
    user = User.objects.create_user(
        username="staff1", password="pass123", email="staff1@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="一般スタッフ", store=store_a, user=user)
    return user


@pytest.fixture
def developer_user(store_a):
    user = User.objects.create_user(
        username="dev", password="pass123", email="dev@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="開発者", store=store_a, user=user, is_developer=True)
    return user


@pytest.fixture
def staff_admin():
    return StaffAdmin(Staff, AdminSite())


@pytest.fixture
def site_settings_admin():
    return SiteSettingsAdmin(SiteSettings, AdminSite())


def _make_request(user):
    factory = RequestFactory()
    request = factory.get('/admin/')
    request.user = user
    return request


# ==============================
# StaffAdmin tests
# ==============================

class TestStaffAdminSaveModel:
    """StaffAdmin.save_model — PIN hashing."""

    def _make_staff(self, store, name="test"):
        user = User.objects.create_user(
            username=f"pin_{name}", password="pass", email=f"pin_{name}@test.com",
        )
        return Staff.objects.create(name=name, store=store, user=user)

    def test_pin_set(self, staff_admin, store_a, superuser):
        """When attendance_pin changes, it gets hashed."""
        staff = self._make_staff(store_a, "pinset")
        form = MagicMock()
        form.changed_data = ['attendance_pin']
        form.cleaned_data = {'attendance_pin': '1234'}
        request = _make_request(superuser)

        with patch.object(staff, 'set_attendance_pin') as mock_set:
            staff_admin.save_model(request, staff, form, change=True)
            mock_set.assert_called_once_with('1234')

    def test_pin_cleared(self, staff_admin, store_a, superuser):
        """When attendance_pin is empty, it clears the pin."""
        staff = self._make_staff(store_a, "pinclear")
        form = MagicMock()
        form.changed_data = ['attendance_pin']
        form.cleaned_data = {'attendance_pin': ''}
        request = _make_request(superuser)

        staff_admin.save_model(request, staff, form, change=True)
        assert staff.attendance_pin == ''

    def test_no_pin_change(self, staff_admin, store_a, superuser):
        """When attendance_pin not changed, nothing happens."""
        staff = self._make_staff(store_a, "nopin")
        form = MagicMock()
        form.changed_data = ['name']
        request = _make_request(superuser)

        with patch.object(staff, 'set_attendance_pin') as mock_set:
            staff_admin.save_model(request, staff, form, change=True)
            mock_set.assert_not_called()


class TestStaffAdminGetQueryset:
    """StaffAdmin.get_queryset — role-based filtering."""

    def _make_staff(self, store, name):
        user = User.objects.create_user(
            username=f"qs_{name}", password="pass", email=f"qs_{name}@test.com",
        )
        return Staff.objects.create(name=name, store=store, user=user)

    def test_superuser_sees_all(self, staff_admin, superuser, store_a, store_b):
        self._make_staff(store_a, "A1")
        self._make_staff(store_b, "B1")
        request = _make_request(superuser)
        qs = staff_admin.get_queryset(request)
        assert qs.count() >= 2

    def test_manager_sees_own_store(self, staff_admin, manager_user, store_a, store_b):
        self._make_staff(store_b, "B1")
        request = _make_request(manager_user)
        qs = staff_admin.get_queryset(request)
        for s in qs:
            assert s.store == store_a

    def test_regular_staff_sees_self(self, staff_admin, regular_staff_user):
        request = _make_request(regular_staff_user)
        qs = staff_admin.get_queryset(request)
        assert qs.count() == 1
        assert qs.first().user == regular_staff_user


class TestStaffAdminPermissions:
    """StaffAdmin.has_change_permission."""

    def _make_staff(self, store, name):
        user = User.objects.create_user(
            username=f"perm_{name}", password="pass", email=f"perm_{name}@test.com",
        )
        return Staff.objects.create(name=name, store=store, user=user)

    def test_superuser_can_change_any(self, staff_admin, superuser, store_a):
        staff = self._make_staff(store_a, "any")
        request = _make_request(superuser)
        assert staff_admin.has_change_permission(request, staff) is True

    def test_manager_can_change_any(self, staff_admin, manager_user, store_a):
        staff = self._make_staff(store_a, "another")
        request = _make_request(manager_user)
        assert staff_admin.has_change_permission(request, staff) is True

    def test_regular_can_change_self(self, staff_admin, regular_staff_user):
        staff = Staff.objects.get(user=regular_staff_user)
        request = _make_request(regular_staff_user)
        assert staff_admin.has_change_permission(request, staff) is True

    def test_regular_cannot_change_other(self, staff_admin, regular_staff_user, store_a):
        other = self._make_staff(store_a, "other")
        request = _make_request(regular_staff_user)
        assert staff_admin.has_change_permission(request, other) is False


# ==============================
# SiteSettingsAdmin tests
# ==============================

class TestSiteSettingsAdmin:
    """SiteSettingsAdmin — singleton behavior."""

    def test_has_add_when_empty(self, site_settings_admin, superuser):
        """Can add when no SiteSettings exists."""
        SiteSettings.objects.all().delete()
        request = _make_request(superuser)
        assert site_settings_admin.has_add_permission(request) is True

    def test_no_add_when_exists(self, site_settings_admin, superuser):
        """Cannot add when SiteSettings already exists."""
        SiteSettings.load()  # creates singleton
        request = _make_request(superuser)
        assert site_settings_admin.has_add_permission(request) is False

    def test_cannot_delete(self, site_settings_admin, superuser):
        """SiteSettings cannot be deleted."""
        request = _make_request(superuser)
        assert site_settings_admin.has_delete_permission(request) is False

    def test_changelist_redirects(self, site_settings_admin, superuser):
        """changelist_view redirects to the singleton's change page."""
        obj = SiteSettings.load()
        request = _make_request(superuser)
        resp = site_settings_admin.changelist_view(request)
        assert resp.status_code == 302
        assert f'{obj.pk}' in resp.url


# ==============================
# get_line_profile tests
# ==============================

class TestGetLineProfile:
    """booking.utils.get_line_profile"""

    @patch('booking.utils.requests.get')
    def test_success(self, mock_get):
        """200 → returns JSON."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'userId': 'U123', 'displayName': 'Test'}
        mock_get.return_value = mock_resp

        result = get_line_profile('valid-token')
        assert result['userId'] == 'U123'
        mock_get.assert_called_once()

    @patch('booking.utils.requests.get')
    def test_failure(self, mock_get):
        """Non-200 → raises Exception."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        with pytest.raises(Exception, match='Failed to get line profile'):
            get_line_profile('bad-token')


# ==============================
# send_line_notify tests
# ==============================

class TestSendLineNotify:
    """booking.line_notify.send_line_notify"""

    def test_no_token(self, settings):
        """Missing token → returns False."""
        settings.LINE_NOTIFY_TOKEN = None
        assert send_line_notify('test') is False

    @patch('booking.line_notify.requests.post')
    def test_success(self, mock_post, settings):
        """200 → returns True."""
        settings.LINE_NOTIFY_TOKEN = 'test-token'
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        assert send_line_notify('hello') is True
        mock_post.assert_called_once()

    @patch('booking.line_notify.time.sleep')
    @patch('booking.line_notify.requests.post')
    def test_rate_limit_retry(self, mock_post, mock_sleep, settings):
        """429 → retries, then succeeds."""
        settings.LINE_NOTIFY_TOKEN = 'test-token'
        rate_resp = MagicMock(status_code=429, text='rate limited')
        ok_resp = MagicMock(status_code=200)
        mock_post.side_effect = [rate_resp, ok_resp]

        assert send_line_notify('hello') is True
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2^0

    @patch('booking.line_notify.time.sleep')
    @patch('booking.line_notify.requests.post')
    def test_rate_limit_exhausted(self, mock_post, mock_sleep, settings):
        """429 every time → returns False."""
        settings.LINE_NOTIFY_TOKEN = 'test-token'
        rate_resp = MagicMock(status_code=429, text='rate limited')
        mock_post.return_value = rate_resp

        assert send_line_notify('hello', max_retries=3) is False
        assert mock_post.call_count == 3

    @patch('booking.line_notify.requests.post')
    def test_server_error(self, mock_post, settings):
        """500 → returns False immediately (no retry)."""
        settings.LINE_NOTIFY_TOKEN = 'test-token'
        mock_resp = MagicMock(status_code=500, text='Internal Server Error')
        mock_post.return_value = mock_resp

        assert send_line_notify('hello') is False
        assert mock_post.call_count == 1

    @patch('booking.line_notify.time.sleep')
    @patch('booking.line_notify.requests.post')
    def test_network_error(self, mock_post, mock_sleep, settings):
        """RequestException → retries with backoff."""
        import requests as req
        settings.LINE_NOTIFY_TOKEN = 'test-token'
        mock_post.side_effect = req.RequestException('timeout')

        assert send_line_notify('hello', max_retries=2) is False
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(1)  # 2^0


# ==============================
# StaffForm tests
# ==============================

class TestStaffForm:
    """booking.forms.StaffForm"""

    def test_valid_form(self, store_a):
        from booking.forms import StaffForm
        form = StaffForm(data={
            'name': 'テスト',
            'price': 5000,
        })
        # StaffForm only validates name, thumbnail, introduction, price
        assert form.is_valid()

    def test_missing_name(self):
        from booking.forms import StaffForm
        form = StaffForm(data={'name': '', 'price': 5000})
        assert not form.is_valid()
        assert 'name' in form.errors


# ==============================
# Sidebar Feature Toggle tests
# ==============================

class TestSidebarFeatureToggles:
    """SiteSettings の show_admin_* トグルが正しくサイドバーを制御するか"""

    @pytest.fixture
    def site_settings(self, db):
        return SiteSettings.load()

    @pytest.fixture
    def admin_site(self):
        from booking.admin_site import custom_site
        return custom_site

    @pytest.fixture
    def manager_request(self, store_a):
        """manager ロールのリクエスト"""
        user = User.objects.create_user(
            username='toggle_mgr', password='pass123',
            email='mgr@test.com', is_staff=True,
        )
        Staff.objects.create(
            user=user, store=store_a, name='Toggle Manager',
            is_store_manager=True, staff_type='store_staff',
        )
        factory = RequestFactory()
        request = factory.get('/admin/')
        request.user = user
        return request

    def _get_slugs(self, admin_site, request):
        """admin_site.get_app_list() から slug 一覧を取得"""
        app_list = admin_site.get_app_list(request)
        return [app.get('slug', '') for app in app_list]

    def test_all_toggles_on_by_default(self, site_settings, admin_site, manager_request):
        """全トグルON（デフォルト）で manager は全グループ表示"""
        slugs = self._get_slugs(admin_site, manager_request)
        for expected in ['reservation', 'shift', 'staff_manage', 'menu_manage',
                         'order', 'pos', 'kitchen', 'table_order']:
            assert expected in slugs, f'{expected} should be visible when toggle is ON'

    def test_toggle_off_hides_group(self, site_settings, admin_site, manager_request):
        """トグルOFFでグループが非表示になる"""
        toggle_slug_pairs = [
            ('show_admin_reservation', 'reservation'),
            ('show_admin_shift', 'shift'),
            ('show_admin_staff_manage', 'staff_manage'),
            ('show_admin_menu_manage', 'menu_manage'),
            ('show_admin_order', 'order'),
            ('show_admin_pos', 'pos'),
            ('show_admin_kitchen', 'kitchen'),
            ('show_admin_table_order', 'table_order'),
            ('show_admin_iot', 'iot'),
        ]
        for field, slug in toggle_slug_pairs:
            # Reset all toggles to True
            for f, _ in toggle_slug_pairs:
                setattr(site_settings, f, True)
            # Turn off this one
            setattr(site_settings, field, False)
            site_settings.save()
            # Clear menu config cache
            from booking.admin_site import invalidate_menu_config_cache
            invalidate_menu_config_cache()

            slugs = self._get_slugs(admin_site, manager_request)
            assert slug not in slugs, f'{slug} should be hidden when {field}=False'

    def test_toggle_off_does_not_affect_other_groups(self, site_settings, admin_site, manager_request):
        """1つのトグルOFFが他のグループに影響しない"""
        site_settings.show_admin_pos = False
        site_settings.save()
        from booking.admin_site import invalidate_menu_config_cache
        invalidate_menu_config_cache()

        slugs = self._get_slugs(admin_site, manager_request)
        assert 'pos' not in slugs
        assert 'shift' in slugs
        assert 'order' in slugs
        assert 'menu_manage' in slugs
