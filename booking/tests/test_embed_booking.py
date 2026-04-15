"""Tests for iframe embed booking flow (embed_token based)."""
import datetime
import hashlib
import secrets
from unittest.mock import patch

from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from booking.models import Store, Staff, Schedule, SiteSettings
from booking.models.shifts import StoreScheduleConfig


def _setup_embed_store(name='テスト店舗'):
    """Create a store with embed enabled and API key."""
    store = Store.objects.create(
        name=name,
        embed_api_key='test-api-key-123',
        embed_allowed_domains='https://example.com',
    )
    StoreScheduleConfig.objects.create(
        store=store, open_hour=10, close_hour=20, slot_duration=60,
    )
    # Enable embed globally
    site = SiteSettings.load()
    site.embed_enabled = True
    site.save()
    return store


def _setup_staff(store, name='テストスタッフ', price=3000):
    """Create a fortune_teller staff."""
    from django.contrib.auth.models import User
    user = User.objects.create_user(
        username=f'staff_{secrets.token_hex(4)}', password='pass')
    return Staff.objects.create(
        user=user, store=store, name=name,
        staff_type='fortune_teller', price=price,
    )


def _create_embed_schedule(staff, store, minutes_ago=1):
    """Create a temporary schedule with embed_token."""
    now = timezone.now()
    return Schedule.objects.create(
        staff=staff,
        store=store,
        start=now + datetime.timedelta(hours=2),
        end=now + datetime.timedelta(hours=3),
        is_temporary=True,
        price=staff.price,
        temporary_booked_at=now - datetime.timedelta(minutes=minutes_ago),
        embed_token=secrets.token_urlsafe(32),
    )


class EmbedStaffCalendarViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)

    def test_calendar_renders(self):
        resp = self.client.get(
            f'/embed/calendar/{self.store.pk}/{self.staff.pk}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.staff.name)

    def test_calendar_with_date(self):
        resp = self.client.get(
            f'/embed/calendar/{self.store.pk}/{self.staff.pk}/2026/4/7/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)

    def test_calendar_bad_api_key(self):
        resp = self.client.get(
            f'/embed/calendar/{self.store.pk}/{self.staff.pk}/',
            {'api_key': 'wrong-key'})
        self.assertEqual(resp.status_code, 403)

    def test_calendar_no_api_key(self):
        resp = self.client.get(
            f'/embed/calendar/{self.store.pk}/{self.staff.pk}/')
        self.assertEqual(resp.status_code, 403)


class EmbedPreBookingViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)

    def test_get_prebooking(self):
        resp = self.client.get(
            f'/embed/prebooking/{self.store.pk}/{self.staff.pk}/2026/4/10/14/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.staff.name)

    def test_get_prebooking_with_minute(self):
        resp = self.client.get(
            f'/embed/prebooking/{self.store.pk}/{self.staff.pk}/2026/4/10/14/30/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)

    def test_post_creates_schedule_with_embed_token(self):
        resp = self.client.post(
            f'/embed/prebooking/{self.store.pk}/{self.staff.pk}/2026/4/10/14/?api_key=test-api-key-123')
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/embed/channel-choice/', resp.url)

        schedule = Schedule.objects.filter(
            staff=self.staff, is_temporary=True).first()
        self.assertIsNotNone(schedule)
        self.assertIsNotNone(schedule.embed_token)
        self.assertEqual(len(schedule.embed_token), 43)

    def test_post_double_booking_shows_error(self):
        # Create existing booking
        start = datetime.datetime(2026, 4, 10, 14, 0)
        Schedule.objects.create(
            staff=self.staff, store=self.store,
            start=start,
            end=start + datetime.timedelta(hours=1),
            is_temporary=False, is_cancelled=False,
            price=3000,
        )
        resp = self.client.post(
            f'/embed/prebooking/{self.store.pk}/{self.staff.pk}/2026/4/10/14/?api_key=test-api-key-123')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '入れ違い')


class EmbedChannelChoiceViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)
        self.schedule = _create_embed_schedule(self.staff, self.store)

    def test_channel_choice_renders(self):
        resp = self.client.get(
            f'/embed/channel-choice/{self.schedule.embed_token}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'LINE')
        self.assertContains(resp, 'メール')

    def test_expired_token(self):
        self.schedule.temporary_booked_at = (
            timezone.now() - datetime.timedelta(minutes=20))
        self.schedule.save()
        resp = self.client.get(
            f'/embed/channel-choice/{self.schedule.embed_token}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 410)

    def test_invalid_token(self):
        resp = self.client.get(
            '/embed/channel-choice/invalid-token-123/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 410)


class EmbedEmailBookingViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)
        self.schedule = _create_embed_schedule(self.staff, self.store)

    def test_get_email_form(self):
        resp = self.client.get(
            f'/embed/email/{self.schedule.embed_token}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'customer_name')

    @patch('booking.views_embed.send_mail')
    def test_post_email_sends_otp(self, mock_mail):
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/?api_key=test-api-key-123',
            {'customer_name': 'テスト太郎', 'customer_email': 'test@example.com'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/verify/', resp.url)
        mock_mail.assert_called_once()

        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.customer_name, 'テスト太郎')
        self.assertEqual(self.schedule.customer_email, 'test@example.com')
        self.assertIsNotNone(self.schedule.email_otp_hash)

    def test_post_missing_fields(self):
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/?api_key=test-api-key-123',
            {'customer_name': '', 'customer_email': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '入力してください')


class EmbedEmailVerifyViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store, price=0)
        self.schedule = _create_embed_schedule(self.staff, self.store)
        # Set up OTP on schedule
        self.otp = '123456'
        self.schedule.customer_name = 'テスト太郎'
        self.schedule.customer_email = 'test@example.com'
        self.schedule.email_otp_hash = hashlib.sha256(
            self.otp.encode('utf-8')).hexdigest()
        self.schedule.email_otp_expires = (
            timezone.now() + datetime.timedelta(minutes=10))
        self.schedule.booking_channel = 'email'
        self.schedule.save()

    def test_get_verify_form(self):
        resp = self.client.get(
            f'/embed/email/{self.schedule.embed_token}/verify/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'test@example.com')

    def test_correct_otp_free_booking_completes(self):
        """Price=0 should immediately confirm."""
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/verify/?api_key=test-api-key-123',
            {'otp': self.otp})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '予約が完了')
        self.schedule.refresh_from_db()
        self.assertFalse(self.schedule.is_temporary)

    def test_wrong_otp(self):
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/verify/?api_key=test-api-key-123',
            {'otp': '000000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '認証コードが正しくありません')

    def test_expired_otp(self):
        self.schedule.email_otp_expires = (
            timezone.now() - datetime.timedelta(minutes=1))
        self.schedule.save()
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/verify/?api_key=test-api-key-123',
            {'otp': self.otp})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '有効期限')


class EmbedEmailVerifyPaidTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store, price=5000)
        self.schedule = _create_embed_schedule(self.staff, self.store)
        self.otp = '654321'
        self.schedule.customer_name = '有料テスト'
        self.schedule.customer_email = 'paid@example.com'
        self.schedule.email_otp_hash = hashlib.sha256(
            self.otp.encode('utf-8')).hexdigest()
        self.schedule.email_otp_expires = (
            timezone.now() + datetime.timedelta(minutes=10))
        self.schedule.booking_channel = 'email'
        self.schedule.save()

    @patch('booking.views_embed.send_mail')
    @patch('booking.views_embed._create_coiney_payment',
           return_value='https://pay.example.com/xxx')
    def test_paid_booking_sends_payment_url(self, mock_pay, mock_mail):
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/verify/?api_key=test-api-key-123',
            {'otp': self.otp})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '決済URL')
        mock_pay.assert_called_once()
        mock_mail.assert_called_once()
        self.schedule.refresh_from_db()
        self.assertEqual(
            self.schedule.payment_url, 'https://pay.example.com/xxx')


class EmbedLineRedirectViewTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)
        self.schedule = _create_embed_schedule(self.staff, self.store)

    def test_line_redirect_sets_session_and_redirects(self):
        resp = self.client.get(
            f'/embed/line/{self.schedule.embed_token}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 302)
        self.assertIn('line_enter', resp.url)

        # Schedule should still exist but embed_token should be cleared
        self.assertTrue(
            Schedule.objects.filter(pk=self.schedule.pk).exists())
        self.schedule.refresh_from_db()
        self.assertIsNone(self.schedule.embed_token)

        # Session should have temporary_booking
        session = self.client.session
        self.assertIn('temporary_booking', session)
        self.assertEqual(
            session['temporary_booking']['staff_id'], self.staff.pk)

    def test_expired_token_returns_410(self):
        self.schedule.temporary_booked_at = (
            timezone.now() - datetime.timedelta(minutes=20))
        self.schedule.save()
        resp = self.client.get(
            f'/embed/line/{self.schedule.embed_token}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 410)


class EmbedTokenMixinTest(TestCase):
    """Test embed_token lookup logic."""

    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)

    def test_valid_token_returns_schedule(self):
        schedule = _create_embed_schedule(self.staff, self.store)
        from booking.views_embed import EmbedTokenMixin
        mixin = EmbedTokenMixin()
        result = mixin.get_embed_schedule(schedule.embed_token)
        self.assertEqual(result.pk, schedule.pk)

    def test_expired_token_returns_none(self):
        schedule = _create_embed_schedule(
            self.staff, self.store, minutes_ago=20)
        from booking.views_embed import EmbedTokenMixin
        mixin = EmbedTokenMixin()
        result = mixin.get_embed_schedule(schedule.embed_token)
        self.assertIsNone(result)

    def test_cancelled_token_returns_none(self):
        schedule = _create_embed_schedule(self.staff, self.store)
        schedule.is_cancelled = True
        schedule.save()
        from booking.views_embed import EmbedTokenMixin
        mixin = EmbedTokenMixin()
        result = mixin.get_embed_schedule(schedule.embed_token)
        self.assertIsNone(result)

    def test_confirmed_token_returns_none(self):
        schedule = _create_embed_schedule(self.staff, self.store)
        schedule.is_temporary = False
        schedule.save()
        from booking.views_embed import EmbedTokenMixin
        mixin = EmbedTokenMixin()
        result = mixin.get_embed_schedule(schedule.embed_token)
        self.assertIsNone(result)


class EmbedEmailValidationTest(TestCase):
    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)
        self.schedule = _create_embed_schedule(self.staff, self.store)

    def test_invalid_email_rejected(self):
        resp = self.client.post(
            f'/embed/email/{self.schedule.embed_token}/?api_key=test-api-key-123',
            {'customer_name': 'テスト', 'customer_email': 'not-an-email'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '形式が正しくありません')


class BookingCalendarLinkTest(TestCase):
    """Test that booking_calendar.html links to embed calendar."""

    def setUp(self):
        self.store = _setup_embed_store()
        self.staff = _setup_staff(self.store)

    def test_links_to_embed_calendar(self):
        resp = self.client.get(
            f'/embed/booking/{self.store.pk}/',
            {'api_key': 'test-api-key-123'})
        self.assertEqual(resp.status_code, 200)
        # Should NOT contain target="_top"
        self.assertNotContains(resp, 'target="_top"')
        # Should contain embed calendar link
        self.assertContains(resp, f'/embed/calendar/{self.store.pk}/')
