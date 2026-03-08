"""Tests for MyPage, MyPageCalendar, and related views."""
import datetime
import pytest
from django.test import Client
from django.urls import reverse, NoReverseMatch
from django.utils import timezone

from booking.models import Staff, Schedule


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


class TestMyPageView:
    """Tests for MyPage view."""

    @pytest.mark.django_db
    def test_requires_login(self, api_client):
        """MyPage redirects unauthenticated users."""
        url = reverse('booking:my_page')
        resp = api_client.get(url)
        assert resp.status_code == 302

    @pytest.mark.django_db
    def test_returns_200(self, authenticated_client):
        """MyPage returns 200 for authenticated user."""
        url = reverse('booking:my_page')
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_context_has_staff_list(self, authenticated_client, staff):
        """MyPage context includes staff_list for current user."""
        url = reverse('booking:my_page')
        resp = authenticated_client.get(url)
        assert 'staff_list' in resp.context
        staff_names = [s.name for s in resp.context['staff_list']]
        assert staff.name in staff_names

    @pytest.mark.django_db
    def test_context_has_schedule_list(self, authenticated_client, staff):
        """MyPage context includes schedule_list with future schedules."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now + datetime.timedelta(hours=1),
            end=now + datetime.timedelta(hours=2),
            is_temporary=False,
        )
        url = reverse('booking:my_page')
        resp = authenticated_client.get(url)
        assert 'schedule_list' in resp.context
        assert schedule in resp.context['schedule_list']

    @pytest.mark.django_db
    def test_context_excludes_past_schedules(self, authenticated_client, staff):
        """MyPage context excludes past schedules."""
        now = timezone.now()
        past_schedule = Schedule.objects.create(
            staff=staff,
            start=now - datetime.timedelta(hours=2),
            end=now - datetime.timedelta(hours=1),
            is_temporary=False,
        )
        url = reverse('booking:my_page')
        resp = authenticated_client.get(url)
        assert past_schedule not in resp.context['schedule_list']


class TestMyPageCalendar:
    """Tests for MyPageCalendar view."""

    @pytest.mark.django_db
    def test_returns_200_for_own_staff(self, authenticated_client, staff):
        """Calendar returns 200 for user's own staff."""
        url = reverse('booking:my_page_calendar', kwargs={'pk': staff.pk})
        resp = authenticated_client.get(url)
        assert resp.status_code == 200

    @pytest.mark.django_db
    def test_denied_for_other_users_staff(self, db, store):
        """Calendar returns 403 for another user's staff."""
        # Create second user and staff
        from django.contrib.auth.models import User
        user2 = User.objects.create_user(username='otheruser', password='pass123')
        staff2 = Staff.objects.create(name='Other Staff', store=store, user=user2)

        # Create first user and login
        user1 = User.objects.create_user(username='viewer', password='pass456')
        Staff.objects.create(name='Viewer Staff', store=store, user=user1)
        client = Client()
        client.login(username='viewer', password='pass456')

        url = reverse('booking:my_page_calendar', kwargs={'pk': staff2.pk})
        resp = client.get(url)
        assert resp.status_code == 403


class TestMyPageHolidayAdd:
    """Tests for my_page_holiday_add function view."""

    @pytest.mark.django_db
    def test_creates_schedule(self, authenticated_client, staff):
        """my_page_holiday_add creates a Schedule for the given hour."""
        url = reverse(
            'booking:my_page_holiday_add',
            kwargs={'pk': staff.pk, 'year': 2025, 'month': 5, 'day': 10, 'hour': 10},
        )
        resp = authenticated_client.post(url)
        assert resp.status_code == 302
        assert Schedule.objects.filter(
            staff=staff,
            start__year=2025,
            start__month=5,
            start__day=10,
        ).exists()

    @pytest.mark.django_db
    def test_requires_permission(self, db, store):
        """my_page_holiday_add raises 403 for unauthorized user."""
        from django.contrib.auth.models import User
        owner = User.objects.create_user(username='owner', password='pass')
        target_staff = Staff.objects.create(name='Target', store=store, user=owner)

        other = User.objects.create_user(username='other', password='pass')
        Staff.objects.create(name='Other', store=store, user=other)
        client = Client()
        client.login(username='other', password='pass')

        url = reverse(
            'booking:my_page_holiday_add',
            kwargs={'pk': target_staff.pk, 'year': 2025, 'month': 5, 'day': 10, 'hour': 10},
        )
        resp = client.post(url)
        assert resp.status_code == 403


class TestMyPageDayDelete:
    """Tests for my_page_day_delete function view (called directly)."""

    @pytest.mark.django_db
    def test_deletes_empty_blocks(self, staff):
        """my_page_day_delete removes schedule blocks without customers."""
        from django.test import RequestFactory
        from booking.views import my_page_day_delete

        # Create empty block (no customer_name, price=0)
        Schedule.objects.create(
            staff=staff,
            start=datetime.datetime(2025, 5, 10, 10, 0),
            end=datetime.datetime(2025, 5, 10, 11, 0),
            is_temporary=False,
            customer_name=None,
            price=0,
        )
        rf = RequestFactory()
        request = rf.post('/fake/')
        request.user = staff.user

        resp = my_page_day_delete(request, pk=staff.pk, year=2025, month=5, day=10)
        assert resp.status_code == 302
        # Empty blocks should be deleted
        assert not Schedule.objects.filter(
            staff=staff,
            start__year=2025,
            start__month=5,
            start__day=10,
            customer_name__isnull=True,
            price=0,
        ).exists()

    @pytest.mark.django_db
    def test_preserves_customer_bookings(self, staff):
        """my_page_day_delete preserves blocks with customer names."""
        from django.test import RequestFactory
        from booking.views import my_page_day_delete

        Schedule.objects.create(
            staff=staff,
            start=datetime.datetime(2025, 5, 10, 10, 0),
            end=datetime.datetime(2025, 5, 10, 11, 0),
            is_temporary=False,
            customer_name='Customer A',
            price=5000,
        )
        rf = RequestFactory()
        request = rf.post('/fake/')
        request.user = staff.user

        my_page_day_delete(request, pk=staff.pk, year=2025, month=5, day=10)
        # Customer bookings should still exist
        assert Schedule.objects.filter(
            staff=staff,
            customer_name='Customer A',
        ).exists()
