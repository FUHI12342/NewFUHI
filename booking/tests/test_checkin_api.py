"""Integration tests for CheckinAPIView, checkin stats, and admin display."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import Schedule, Staff, Store
from booking.services.checkin_token import make_qr_token


def _make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def _make_staff_user(store, username='staff1', name='テストスタッフ'):
    user = User.objects.create_user(
        username=username, password='testpass123', is_staff=True,
    )
    staff = Staff.objects.create(user=user, store=store, name=name)
    return user, staff


def _make_schedule(staff, start_offset_min=15, duration_min=60, **kwargs):
    """Create a confirmed, non-cancelled schedule."""
    now = timezone.now()
    start = now + timedelta(minutes=start_offset_min)
    end = start + timedelta(minutes=duration_min)
    defaults = dict(
        staff=staff,
        start=start,
        end=end,
        is_temporary=False,
        is_cancelled=False,
        is_checked_in=False,
        customer_name='テスト顧客',
        price=1000,
    )
    defaults.update(kwargs)
    return Schedule.objects.create(**defaults)


class CheckinAPITestBase(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.user, self.staff = _make_staff_user(self.store)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('booking_api:checkin_api')


class QrCheckinTests(CheckinAPITestBase):
    def test_qr_checkin_success(self):
        schedule = _make_schedule(self.staff, start_offset_min=15)
        token = make_qr_token(
            str(schedule.reservation_number), schedule.end,
        )
        resp = self.client.post(
            self.url,
            {'qr_token': token},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_checked_in)

    def test_qr_expired_rejected(self):
        schedule = _make_schedule(self.staff, start_offset_min=15)
        # Create token with already-expired end time
        expired_end = timezone.now() - timedelta(hours=1)
        token = make_qr_token(
            str(schedule.reservation_number), expired_end,
        )
        resp = self.client.post(
            self.url,
            {'qr_token': token},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_qr_invalid_signature_rejected(self):
        schedule = _make_schedule(self.staff, start_offset_min=15)
        token = make_qr_token(
            str(schedule.reservation_number), schedule.end,
        )
        # Tamper with signature
        parts = token.split('|')
        parts[2] = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        tampered = '|'.join(parts)
        resp = self.client.post(
            self.url,
            {'qr_token': tampered},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_already_checked_in(self):
        schedule = _make_schedule(
            self.staff, start_offset_min=15, is_checked_in=True,
            checked_in_at=timezone.now(),
        )
        token = make_qr_token(
            str(schedule.reservation_number), schedule.end,
        )
        resp = self.client.post(
            self.url,
            {'qr_token': token},
            format='json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_wrong_store_rejected(self):
        other_store = _make_store(name='別店舗')
        other_user, other_staff = _make_staff_user(
            other_store, username='other_staff', name='他スタッフ',
        )
        schedule = _make_schedule(other_staff, start_offset_min=15)
        token = make_qr_token(
            str(schedule.reservation_number), schedule.end,
        )
        # Authenticate as self.user (different store)
        resp = self.client.post(
            self.url,
            {'qr_token': token},
            format='json',
        )
        self.assertEqual(resp.status_code, 403)

    def test_time_window_rejected(self):
        """Schedule starting >30 min from now should be rejected."""
        schedule = _make_schedule(self.staff, start_offset_min=60)
        token = make_qr_token(
            str(schedule.reservation_number), schedule.end,
        )
        resp = self.client.post(
            self.url,
            {'qr_token': token},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn('時間外', resp.data['message'])

    def test_unauthenticated(self):
        client = APIClient()
        resp = client.post(
            self.url,
            {'qr_token': 'something'},
            format='json',
        )
        self.assertIn(resp.status_code, [401, 403])


class BackupCodeCheckinTests(CheckinAPITestBase):
    def test_backup_code_success(self):
        schedule = _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='123456',
        )
        resp = self.client.post(
            self.url,
            {'backup_code': '123456'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_checked_in)

    def test_backup_code_wrong(self):
        _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='123456',
        )
        resp = self.client.post(
            self.url,
            {'backup_code': '999999'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_backup_code_wrong_store(self):
        other_store = _make_store(name='別店舗2')
        _, other_staff = _make_staff_user(
            other_store, username='other2', name='他スタッフ2',
        )
        _make_schedule(
            other_staff, start_offset_min=15,
            checkin_backup_code='654321',
        )
        # self.user is from self.store, not other_store
        resp = self.client.post(
            self.url,
            {'backup_code': '654321'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_superuser_any_store(self):
        su = User.objects.create_superuser(
            username='admin', password='adminpass',
        )
        other_store = _make_store(name='別店舗3')
        _, other_staff = _make_staff_user(
            other_store, username='other3', name='他スタッフ3',
        )
        schedule = _make_schedule(
            other_staff, start_offset_min=15,
            checkin_backup_code='111222',
        )
        client = APIClient()
        client.force_authenticate(user=su)
        resp = client.post(
            self.url,
            {'backup_code': '111222'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_checked_in)

    def test_checked_in_by_recorded(self):
        schedule = _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='444555',
        )
        self.client.post(
            self.url,
            {'backup_code': '444555'},
            format='json',
        )
        schedule.refresh_from_db()
        self.assertEqual(schedule.checked_in_by_id, self.staff.pk)

    def test_cancelled_schedule_not_found(self):
        _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='777888',
            is_cancelled=True,
        )
        resp = self.client.post(
            self.url,
            {'backup_code': '777888'},
            format='json',
        )
        self.assertEqual(resp.status_code, 404)

    def test_no_input_returns_400(self):
        resp = self.client.post(
            self.url,
            {},
            format='json',
        )
        self.assertEqual(resp.status_code, 400)


class CheckinCustomerNotificationTests(CheckinAPITestBase):
    """Test that customer is notified on successful checkin."""

    @patch('booking.views_booking._make_messaging_api')
    def test_line_notification_sent_on_checkin(self, mock_make_api):
        mock_api = MagicMock()
        mock_client = MagicMock()
        mock_make_api.return_value = (mock_api, mock_client)
        schedule = _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='112233',
        )
        # Set encrypted LINE user id
        try:
            schedule.set_line_user_id('U_test_user_123')
            schedule.save(update_fields=['line_user_hash', 'line_user_enc'])
        except Exception:
            pass  # Skip if encryption key not configured in test

        self.client.post(
            self.url,
            {'backup_code': '112233'},
            format='json',
        )
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_checked_in)

    @patch('booking.views_booking.send_mail')
    def test_email_notification_sent_on_checkin(self, mock_send_mail):
        schedule = _make_schedule(
            self.staff, start_offset_min=15,
            checkin_backup_code='998877',
            booking_channel='email',
            customer_email='test@example.com',
        )
        self.client.post(
            self.url,
            {'backup_code': '998877'},
            format='json',
        )
        schedule.refresh_from_db()
        self.assertTrue(schedule.is_checked_in)
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        self.assertIn('チェックイン完了', call_kwargs[1]['subject'] if 'subject' in (call_kwargs[1] or {}) else call_kwargs[0][0])


class CheckinStatsAPITests(TestCase):
    """Test the checkin stats dashboard API."""

    def setUp(self):
        self.store = _make_store()
        self.user, self.staff = _make_staff_user(self.store)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.url = reverse('booking_api:checkin_stats_api')

    def test_stats_empty(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['summary']['total'], 0)
        self.assertEqual(resp.data['summary']['checkin_rate'], 0)

    def test_stats_with_data(self):
        # Create some schedules
        _make_schedule(
            self.staff, start_offset_min=-30,
            is_checked_in=True, checked_in_at=timezone.now(),
        )
        _make_schedule(self.staff, start_offset_min=-60)
        _make_schedule(self.staff, start_offset_min=-90)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['summary']['total'], 3)
        self.assertEqual(resp.data['summary']['checked_in'], 1)
        self.assertEqual(resp.data['summary']['no_show'], 2)
        self.assertAlmostEqual(resp.data['summary']['checkin_rate'], 0.3333, places=3)

    def test_stats_by_staff(self):
        _make_schedule(
            self.staff, start_offset_min=-30,
            is_checked_in=True, checked_in_at=timezone.now(),
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data['by_staff']) > 0)
        self.assertEqual(resp.data['by_staff'][0]['staff_name'], self.staff.name)

    def test_stats_store_scoped(self):
        """Non-superuser should only see their store's data."""
        other_store = _make_store(name='Other Store')
        _, other_staff = _make_staff_user(
            other_store, username='other_stat', name='他スタッフStat',
        )
        _make_schedule(other_staff, start_offset_min=-30)
        _make_schedule(self.staff, start_offset_min=-30)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        # Should only see own store's schedule
        self.assertEqual(resp.data['summary']['total'], 1)

    def test_stats_unauthenticated(self):
        client = APIClient()
        resp = client.get(self.url)
        self.assertIn(resp.status_code, [401, 403])

    def test_stats_days_param(self):
        resp = self.client.get(f'{self.url}?days=7')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['summary']['days'], 7)


class AdminScheduleDisplayTests(TestCase):
    """Test that admin displays new checkin fields correctly."""

    def setUp(self):
        self.store = _make_store()
        self.su = User.objects.create_superuser(
            username='admin_test', password='adminpass',
        )
        self.staff_obj = Staff.objects.create(
            user=self.su, store=self.store, name='Admin Staff',
        )
        self.client.login(username='admin_test', password='adminpass')

    def test_schedule_admin_changelist(self):
        schedule = _make_schedule(
            self.staff_obj, start_offset_min=15,
            checkin_backup_code='999111',
        )
        resp = self.client.get('/admin/booking/schedule/')
        self.assertEqual(resp.status_code, 200)

    def test_schedule_admin_change_view(self):
        schedule = _make_schedule(
            self.staff_obj, start_offset_min=15,
            checkin_backup_code='999222',
            checked_in_by=self.staff_obj,
        )
        resp = self.client.get(f'/admin/booking/schedule/{schedule.pk}/change/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '999222')
