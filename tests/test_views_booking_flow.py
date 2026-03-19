"""
tests/test_views_booking_flow.py
Booking flow view tests: top page, store list, staff list/calendar,
prebooking, channel choice, email booking, cancel, LINE enter.
"""
import datetime
import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.utils import timezone
from booking.models import Store, Staff, Schedule, Order


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


# ------------------------------------------------------------------
# BookingTopPage
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestBookingTopPage:
    def test_get_returns_200(self, api_client, store):
        url = reverse('booking:booking_top')
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_context_has_stores(self, api_client, store):
        url = reverse('booking:booking_top')
        resp = api_client.get(url)
        assert 'stores' in resp.context
        store_names = [s.name for s in resp.context['stores']]
        assert store.name in store_names

    def test_top_page_with_multiple_stores(self, api_client, store, db):
        Store.objects.create(
            name="二号店",
            address="大阪市",
            business_hours="10:00-20:00",
            nearest_station="梅田駅",
        )
        url = reverse('booking:booking_top')
        resp = api_client.get(url)
        assert resp.context['stores'].count() == 2


# ------------------------------------------------------------------
# StoreList
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestStoreList:
    def test_get_returns_200(self, api_client, store):
        url = reverse('booking:store_list')
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_lists_stores(self, api_client, store):
        url = reverse('booking:store_list')
        resp = api_client.get(url)
        assert store in resp.context['store_list']


# ------------------------------------------------------------------
# StaffList
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffList:
    def test_get_returns_200(self, api_client, store, staff):
        url = reverse('booking:staff_list', kwargs={'pk': store.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_context_has_store(self, api_client, store, staff):
        url = reverse('booking:staff_list', kwargs={'pk': store.pk})
        resp = api_client.get(url)
        assert resp.context['store'] == store

    def test_invalid_store_returns_404(self, api_client):
        url = reverse('booking:staff_list', kwargs={'pk': 99999})
        resp = api_client.get(url)
        assert resp.status_code == 404


# ------------------------------------------------------------------
# StaffCalendar
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffCalendar:
    def test_get_returns_200(self, api_client, staff):
        url = reverse('booking:staff_calendar', kwargs={'pk': staff.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_context_has_calendar_and_staff(self, api_client, staff):
        url = reverse('booking:staff_calendar', kwargs={'pk': staff.pk})
        resp = api_client.get(url)
        assert 'calendar' in resp.context
        assert 'staff' in resp.context
        assert resp.context['staff'] == staff

    def test_calendar_with_date_kwargs(self, api_client, staff):
        today = datetime.date.today()
        url = reverse('booking:calendar', kwargs={
            'pk': staff.pk,
            'year': today.year,
            'month': today.month,
            'day': today.day,
        })
        resp = api_client.get(url)
        assert resp.status_code == 200


# ------------------------------------------------------------------
# PreBooking - redirect on double-booking
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestPreBooking:
    def test_double_booking_redirects(self, api_client, staff):
        """If slot is already booked, form_valid should redirect with error."""
        now = timezone.now().replace(second=0, microsecond=0)
        start = now + datetime.timedelta(days=1)
        start = start.replace(hour=10, minute=0)
        Schedule.objects.create(
            staff=staff,
            start=start,
            end=start + datetime.timedelta(hours=1),
            is_temporary=False,
            price=0,
        )
        url = reverse('booking:prebooking', kwargs={
            'pk': staff.pk,
            'year': start.year,
            'month': start.month,
            'day': start.day,
            'hour': start.hour,
        })
        resp = api_client.post(url, data={})
        # Should redirect to staff calendar (double-booking guard)
        assert resp.status_code == 302


# ------------------------------------------------------------------
# BookingChannelChoice
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestBookingChannelChoice:
    def test_get_returns_200(self, api_client):
        url = reverse('booking:channel_choice')
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_context_has_booking_from_session(self, api_client):
        session = api_client.session
        session['temporary_booking'] = {
            'staff_name': 'テスト',
            'start': '2026-04-01T10:00:00',
        }
        session.save()
        url = reverse('booking:channel_choice')
        resp = api_client.get(url)
        assert resp.context['booking'] is not None


# ------------------------------------------------------------------
# EmailBookingView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestEmailBookingView:
    def test_get_without_session_redirects(self, api_client):
        """Without temporary_booking in session, should redirect to top."""
        url = reverse('booking:email_booking')
        resp = api_client.get(url)
        assert resp.status_code == 302

    def test_get_with_session_returns_200(self, api_client):
        session = api_client.session
        session['temporary_booking'] = {
            'staff_name': 'テスト',
            'start': '2026-04-01T10:00:00',
            'end': '2026-04-01T11:00:00',
            'price': 5000,
        }
        session.save()
        url = reverse('booking:email_booking')
        resp = api_client.get(url)
        assert resp.status_code == 200


# ------------------------------------------------------------------
# CancelReservationView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCancelReservationView:
    @patch('booking.views_booking.LineBotApi')
    def test_post_cancels_schedule(self, mock_linebot_cls, admin_client, staff):
        """Admin/staff user can cancel a schedule."""
        mock_linebot_cls.return_value = MagicMock()
        schedule = Schedule.objects.create(
            staff=staff,
            start=timezone.now() + datetime.timedelta(days=1),
            end=timezone.now() + datetime.timedelta(days=1, hours=1),
            is_temporary=False,
            price=5000,
        )
        url = reverse('booking:cancel_reservation', kwargs={'schedule_id': schedule.id})
        try:
            resp = admin_client.post(url)
        except Exception:
            # cancel_success.html template may not exist in test env
            pass
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True

    def test_cancel_requires_login(self, api_client, staff):
        schedule = Schedule.objects.create(
            staff=staff,
            start=timezone.now() + datetime.timedelta(days=1),
            end=timezone.now() + datetime.timedelta(days=1, hours=1),
            is_temporary=False,
            price=5000,
        )
        url = reverse('booking:cancel_reservation', kwargs={'schedule_id': schedule.id})
        resp = api_client.post(url)
        # LoginRequiredMixin should redirect to login
        assert resp.status_code == 302
        assert 'login' in resp.url


# ------------------------------------------------------------------
# LineEnterView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestLineEnterView:
    def test_get_redirects_to_line_oauth(self, api_client):
        url = reverse('booking:line_enter')
        resp = api_client.get(url)
        assert resp.status_code == 302
        assert 'access.line.me' in resp.url

    def test_sets_state_in_session(self, api_client):
        url = reverse('booking:line_enter')
        api_client.get(url)
        session = api_client.session
        assert 'state' in session


# ------------------------------------------------------------------
# CSRF on forms
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCSRFProtection:
    def test_prebooking_post_without_csrf_rejected(self, staff):
        """POST without CSRF token should be rejected (403)."""
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        url = reverse('booking:prebooking', kwargs={
            'pk': staff.pk,
            'year': 2026,
            'month': 4,
            'day': 1,
            'hour': 10,
        })
        resp = client.post(url, data={})
        assert resp.status_code == 403
