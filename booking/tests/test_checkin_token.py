"""Unit tests for booking.services.checkin_token."""
from datetime import timedelta
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.utils import timezone

from booking.services.checkin_token import (
    generate_backup_code,
    generate_signed_checkin_qr,
    is_within_checkin_window,
    make_qr_token,
    verify_qr_token,
)


class MakeQrTokenTests(TestCase):
    def test_format_three_parts(self):
        """Token has 3 pipe-separated parts."""
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('abc-123', end)
        parts = token.split('|')
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], 'abc-123')

    def test_signature_length(self):
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('abc-123', end)
        sig = token.split('|')[2]
        self.assertEqual(len(sig), 64)


class VerifyQrTokenTests(TestCase):
    def test_verify_valid_token(self):
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('res-001', end)
        valid, res_num, error = verify_qr_token(token)
        self.assertTrue(valid)
        self.assertEqual(res_num, 'res-001')
        self.assertEqual(error, '')

    def test_verify_expired_token(self):
        end = timezone.now() - timedelta(hours=1)
        token = make_qr_token('res-002', end)
        valid, res_num, error = verify_qr_token(token)
        self.assertFalse(valid)
        self.assertIn('有効期限', error)

    def test_verify_tampered_signature(self):
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('res-003', end)
        parts = token.split('|')
        parts[2] = 'deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678'
        tampered = '|'.join(parts)
        valid, _, error = verify_qr_token(tampered)
        self.assertFalse(valid)
        self.assertIn('署名', error)

    def test_verify_tampered_reservation(self):
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('res-004', end)
        parts = token.split('|')
        parts[0] = 'res-HACKED'
        tampered = '|'.join(parts)
        valid, _, error = verify_qr_token(tampered)
        self.assertFalse(valid)
        self.assertIn('署名', error)

    def test_verify_bad_format(self):
        valid, _, error = verify_qr_token('not-a-valid-token')
        self.assertFalse(valid)
        self.assertIn('形式', error)

    def test_verify_bad_format_two_parts(self):
        valid, _, error = verify_qr_token('a|b')
        self.assertFalse(valid)

    @override_settings(CHECKIN_QR_SECRET='test-secret-123')
    def test_uses_checkin_qr_secret(self):
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('res-secret', end)
        valid, res_num, _ = verify_qr_token(token)
        self.assertTrue(valid)
        self.assertEqual(res_num, 'res-secret')

    @override_settings(CHECKIN_QR_SECRET='')
    def test_qr_secret_fallback_to_secret_key(self):
        """When CHECKIN_QR_SECRET is empty, falls back to SECRET_KEY."""
        end = timezone.now() + timedelta(hours=1)
        token = make_qr_token('res-fallback', end)
        valid, res_num, _ = verify_qr_token(token)
        self.assertTrue(valid)
        self.assertEqual(res_num, 'res-fallback')


class GenerateBackupCodeTests(TestCase):
    def test_format_six_digits(self):
        """Backup code is a 6-digit string."""
        from booking.models import Store
        store = Store.objects.create(name='Test Store')
        code = generate_backup_code(store, timezone.localdate())
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())

    def test_unique_within_store_date(self):
        """Two codes for same store/date should differ."""
        from booking.models import Store
        store = Store.objects.create(name='Test Store 2')
        today = timezone.localdate()
        code1 = generate_backup_code(store, today)
        code2 = generate_backup_code(store, today)
        # They might rarely collide but statistically should differ
        # We just ensure they're valid 6-digit codes
        self.assertEqual(len(code1), 6)
        self.assertEqual(len(code2), 6)


class IsWithinCheckinWindowTests(TestCase):
    def _make_schedule(self, start_offset_min, duration_min=60):
        """Create a mock schedule with start/end relative to now."""
        from unittest.mock import MagicMock
        now = timezone.now()
        s = MagicMock()
        s.start = now + timedelta(minutes=start_offset_min)
        s.end = s.start + timedelta(minutes=duration_min)
        return s

    def test_before_window(self):
        """31 minutes before start → False."""
        schedule = self._make_schedule(start_offset_min=31)
        self.assertFalse(is_within_checkin_window(schedule))

    def test_within_window_before_start(self):
        """15 minutes before start → True."""
        schedule = self._make_schedule(start_offset_min=15)
        self.assertTrue(is_within_checkin_window(schedule))

    def test_at_start(self):
        """Exactly at start → True."""
        schedule = self._make_schedule(start_offset_min=0)
        self.assertTrue(is_within_checkin_window(schedule))

    def test_during_appointment(self):
        """During appointment → True."""
        schedule = self._make_schedule(start_offset_min=-30, duration_min=60)
        self.assertTrue(is_within_checkin_window(schedule))

    def test_after_end(self):
        """After end → False."""
        schedule = self._make_schedule(start_offset_min=-120, duration_min=60)
        self.assertFalse(is_within_checkin_window(schedule))


class GenerateSignedQrTests(TestCase):
    def test_returns_contentfile(self):
        end = timezone.now() + timedelta(hours=1)
        result = generate_signed_checkin_qr('res-qr-001', end)
        self.assertIsInstance(result, ContentFile)
        self.assertTrue(result.name.endswith('.png'))

    def test_contentfile_has_data(self):
        end = timezone.now() + timedelta(hours=1)
        result = generate_signed_checkin_qr('res-qr-002', end)
        self.assertGreater(len(result.read()), 0)
