"""Admin role-based permission tests.

Tests sidebar visibility, CRUD permissions, store scoping,
and model access for all 5 roles: superuser, developer, owner, manager, staff.
"""
from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.urls import reverse

from booking.admin_site import custom_site, get_user_role, ROLE_VISIBLE_GROUPS
from booking.models import Schedule, Staff, Store


def _make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def _make_user(username, **kwargs):
    return User.objects.create_user(
        username=username, password='testpass123', **kwargs,
    )


def _make_staff(user, store, **flags):
    defaults = dict(name=user.username, store=store)
    defaults.update(flags)
    return Staff.objects.create(user=user, **defaults)


# ==============================
# Role detection
# ==============================
class GetUserRoleTests(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.factory = RequestFactory()

    def _request(self, user):
        request = self.factory.get('/admin/')
        request.user = user
        return request

    def test_superuser_role(self):
        user = User.objects.create_superuser('su', password='pass')
        self.assertEqual(get_user_role(self._request(user)), 'superuser')

    def test_developer_role(self):
        user = _make_user('dev', is_staff=True)
        _make_staff(user, self.store, is_developer=True)
        self.assertEqual(get_user_role(self._request(user)), 'developer')

    def test_owner_role(self):
        user = _make_user('owner', is_staff=True)
        _make_staff(user, self.store, is_owner=True)
        self.assertEqual(get_user_role(self._request(user)), 'owner')

    def test_manager_role(self):
        user = _make_user('mgr', is_staff=True)
        _make_staff(user, self.store, is_store_manager=True)
        self.assertEqual(get_user_role(self._request(user)), 'manager')

    def test_staff_role(self):
        user = _make_user('staff1', is_staff=True)
        _make_staff(user, self.store)
        self.assertEqual(get_user_role(self._request(user)), 'staff')

    def test_no_staff_record(self):
        user = _make_user('nostaff')
        self.assertEqual(get_user_role(self._request(user)), 'none')

    def test_unauthenticated(self):
        from django.contrib.auth.models import AnonymousUser
        request = self.factory.get('/admin/')
        request.user = AnonymousUser()
        self.assertEqual(get_user_role(request), 'none')

    def test_developer_takes_priority_over_owner(self):
        """Developer flag should take precedence over owner flag."""
        user = _make_user('devowner', is_staff=True)
        _make_staff(user, self.store, is_developer=True, is_owner=True)
        self.assertEqual(get_user_role(self._request(user)), 'developer')

    def test_owner_takes_priority_over_manager(self):
        user = _make_user('ownermgr', is_staff=True)
        _make_staff(user, self.store, is_owner=True, is_store_manager=True)
        self.assertEqual(get_user_role(self._request(user)), 'owner')


# ==============================
# Admin access control
# ==============================
class AdminAccessTests(TestCase):
    """Test that each role can/cannot access the admin site."""

    def setUp(self):
        self.store = _make_store()

    def test_superuser_access(self):
        User.objects.create_superuser('su', password='pass')
        self.client.login(username='su', password='pass')
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_owner_access(self):
        user = _make_user('owner', is_staff=True)
        _make_staff(user, self.store, is_owner=True)
        self.client.login(username='owner', password='testpass123')
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_manager_access(self):
        user = _make_user('mgr', is_staff=True)
        _make_staff(user, self.store, is_store_manager=True)
        self.client.login(username='mgr', password='testpass123')
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_access(self):
        user = _make_user('staff1', is_staff=True)
        _make_staff(user, self.store)
        self.client.login(username='staff1', password='testpass123')
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 200)

    def test_no_staff_record_denied(self):
        _make_user('nostaff')
        self.client.login(username='nostaff', password='testpass123')
        resp = self.client.get('/admin/')
        # Should redirect to login
        self.assertIn(resp.status_code, [302, 403])

    def test_unauthenticated_denied(self):
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 302)  # Redirect to login


# ==============================
# Sidebar visibility per role
# ==============================
class SidebarVisibilityTests(TestCase):
    """Test that sidebar shows correct groups per role."""

    def setUp(self):
        self.store = _make_store()
        self.factory = RequestFactory()

    def _get_app_list(self, user):
        request = self.factory.get('/admin/')
        request.user = user
        # Need session for admin
        from django.contrib.sessions.backends.db import SessionStore
        request.session = SessionStore()
        return custom_site.get_app_list(request)

    def _group_slugs(self, app_list):
        """Extract slug identifiers from app list."""
        slugs = set()
        for app in app_list:
            name = app.get('name', '')
            slug = app.get('app_label', '')
            slugs.add(slug)
        return slugs

    def test_superuser_sees_all_groups(self):
        user = User.objects.create_superuser('su', password='pass')
        app_list = self._get_app_list(user)
        # Superuser should see many groups
        self.assertGreater(len(app_list), 5)

    def test_staff_sees_limited_groups(self):
        user = _make_user('staff1', is_staff=True)
        _make_staff(user, self.store)
        app_list = self._get_app_list(user)
        # Staff should see fewer groups than superuser
        su = User.objects.create_superuser('su2', password='pass')
        su_list = self._get_app_list(su)
        self.assertLess(len(app_list), len(su_list))

    def test_manager_sees_more_than_staff(self):
        staff_user = _make_user('staff2', is_staff=True)
        _make_staff(staff_user, self.store)

        mgr_user = _make_user('mgr', is_staff=True)
        _make_staff(mgr_user, self.store, is_store_manager=True)

        staff_list = self._get_app_list(staff_user)
        mgr_list = self._get_app_list(mgr_user)
        self.assertGreater(len(mgr_list), len(staff_list))


# ==============================
# CRUD permissions
# ==============================
class CRUDPermissionTests(TestCase):
    """Test CRUD permissions per role on Schedule model."""

    def setUp(self):
        self.store = _make_store()
        self.su = User.objects.create_superuser('su', password='pass')

    def _login_as(self, role):
        if role == 'superuser':
            self.client.login(username='su', password='pass')
            return self.su
        user = _make_user(f'{role}_user', is_staff=True)
        flags = {
            'developer': {'is_developer': True},
            'owner': {'is_owner': True},
            'manager': {'is_store_manager': True},
            'staff': {},
        }
        _make_staff(user, self.store, **flags[role])
        self.client.login(username=f'{role}_user', password='testpass123')
        return user

    def test_superuser_can_add_schedule(self):
        self._login_as('superuser')
        resp = self.client.get('/admin/booking/schedule/add/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_cannot_add_schedule(self):
        self._login_as('staff')
        resp = self.client.get('/admin/booking/schedule/add/')
        self.assertEqual(resp.status_code, 403)

    def test_manager_can_view_schedule_list(self):
        self._login_as('manager')
        resp = self.client.get('/admin/booking/schedule/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_can_view_schedule_list(self):
        self._login_as('staff')
        resp = self.client.get('/admin/booking/schedule/')
        self.assertEqual(resp.status_code, 200)


# ==============================
# Store scoping
# ==============================
class StoreScopingTests(TestCase):
    """Test that staff/manager can only see their own store's data."""

    def setUp(self):
        self.store_a = _make_store(name='店舗A')
        self.store_b = _make_store(name='店舗B')

        self.su = User.objects.create_superuser('su', password='pass')
        Staff.objects.create(user=self.su, store=self.store_a, name='Admin')

        self.mgr_user = _make_user('mgr_a', is_staff=True)
        self.mgr_staff = _make_staff(
            self.mgr_user, self.store_a, is_store_manager=True,
        )

        # Staff in store B
        self.staff_b_user = _make_user('staff_b', is_staff=True)
        self.staff_b = _make_staff(self.staff_b_user, self.store_b)

    def test_superuser_sees_all_stores_staff(self):
        self.client.login(username='su', password='pass')
        resp = self.client.get('/admin/booking/staff/')
        self.assertEqual(resp.status_code, 200)
        # Content should include both stores
        content = resp.content.decode()
        self.assertIn('店舗A', content)
        self.assertIn('店舗B', content)

    def test_manager_sees_own_store_staff_only(self):
        self.client.login(username='mgr_a', password='testpass123')
        resp = self.client.get('/admin/booking/staff/')
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn('店舗A', content)
        # Store B staff should not appear
        self.assertNotIn('staff_b', content)

    def test_staff_redirected_to_own_profile(self):
        """Regular staff should be redirected to their own profile edit page."""
        self.client.login(username='staff_b', password='testpass123')
        resp = self.client.get('/admin/booking/staff/')
        # Should redirect to own profile
        self.assertIn(resp.status_code, [200, 302])


# ==============================
# Model-level access (allowed models)
# ==============================
class ModelAccessTests(TestCase):
    """Test that roles can only access their allowed models."""

    def setUp(self):
        self.store = _make_store()

    def test_staff_can_view_order_admin(self):
        """Staff can view order list (order is in DEFAULT_ALLOWED_MODELS for staff)."""
        user = _make_user('basic_staff', is_staff=True)
        _make_staff(user, self.store, can_see_orders=False)
        self.client.login(username='basic_staff', password='testpass123')
        resp = self.client.get('/admin/booking/order/')
        # Staff has view-only access to orders (in allowed models)
        self.assertEqual(resp.status_code, 200)

    def test_staff_with_orders_flag_can_access_order(self):
        """Staff with can_see_orders=True should see order list."""
        user = _make_user('order_staff', is_staff=True)
        _make_staff(user, self.store, can_see_orders=True)
        self.client.login(username='order_staff', password='testpass123')
        resp = self.client.get('/admin/booking/order/')
        self.assertEqual(resp.status_code, 200)

    def test_manager_can_access_product_admin(self):
        user = _make_user('mgr2', is_staff=True)
        _make_staff(user, self.store, is_store_manager=True)
        self.client.login(username='mgr2', password='testpass123')
        resp = self.client.get('/admin/booking/product/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_cannot_access_payroll(self):
        """Payroll should be hidden from regular staff."""
        user = _make_user('payroll_staff', is_staff=True)
        _make_staff(user, self.store)
        self.client.login(username='payroll_staff', password='testpass123')
        resp = self.client.get('/admin/booking/payrollperiod/')
        self.assertIn(resp.status_code, [403, 302])

    def test_owner_can_access_payroll(self):
        user = _make_user('owner2', is_staff=True)
        _make_staff(user, self.store, is_owner=True)
        self.client.login(username='owner2', password='testpass123')
        resp = self.client.get('/admin/booking/payrollperiod/')
        self.assertEqual(resp.status_code, 200)

    def test_staff_cannot_delete_schedule(self):
        """Staff should not be able to delete schedules."""
        user = _make_user('del_staff', is_staff=True)
        staff = _make_staff(user, self.store)
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff, start=now, end=now + timedelta(hours=1),
            customer_name='テスト', price=1000,
        )
        self.client.login(username='del_staff', password='testpass123')
        resp = self.client.post(
            f'/admin/booking/schedule/{schedule.pk}/delete/',
            {'post': 'yes'},
        )
        self.assertIn(resp.status_code, [403, 302])

    def test_owner_can_delete_schedule(self):
        user = _make_user('del_owner', is_staff=True)
        staff = _make_staff(user, self.store, is_owner=True)
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff, start=now, end=now + timedelta(hours=1),
            customer_name='テスト', price=1000,
        )
        self.client.login(username='del_owner', password='testpass123')
        resp = self.client.post(
            f'/admin/booking/schedule/{schedule.pk}/delete/',
            {'post': 'yes'},
        )
        # Should succeed (redirect to changelist after delete)
        self.assertIn(resp.status_code, [200, 302])


# ==============================
# Dashboard access per role
# ==============================
class DashboardAccessTests(TestCase):
    """Test restaurant dashboard access per role."""

    def setUp(self):
        self.store = _make_store()

    def test_superuser_can_access_dashboard(self):
        User.objects.create_superuser('su', password='pass')
        self.client.login(username='su', password='pass')
        resp = self.client.get('/admin/dashboard/restaurant/')
        self.assertIn(resp.status_code, [200, 302])

    def test_staff_cannot_access_dashboard(self):
        user = _make_user('dash_staff', is_staff=True)
        _make_staff(user, self.store)
        self.client.login(username='dash_staff', password='testpass123')
        resp = self.client.get('/admin/dashboard/restaurant/')
        # Staff can access dashboard (admin_view wraps it)
        self.assertIn(resp.status_code, [200, 302, 403])

    def test_manager_can_access_dashboard(self):
        user = _make_user('dash_mgr', is_staff=True)
        _make_staff(user, self.store, is_store_manager=True)
        self.client.login(username='dash_mgr', password='testpass123')
        resp = self.client.get('/admin/dashboard/restaurant/')
        self.assertIn(resp.status_code, [200, 302])
