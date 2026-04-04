"""
tests/test_line_reminder.py
Tests for booking/services/line_reminder.py:
  - send_day_before_reminders (sends, skips already-sent, skips cancelled)
  - send_same_day_reminders (sends, skips already-sent)
  - Celery task checks feature flag
"""
import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from booking.models import Schedule, SiteSettings
from booking.models.line_customer import LineCustomer


# ==============================================================
# Helpers
# ==============================================================

def _create_schedule_with_line(staff, store, start, **kwargs):
    """Create a Schedule with encrypted LINE user_id fields."""
    schedule = Schedule(
        staff=staff,
        store=store,
        start=start,
        end=start + timedelta(hours=1),
        customer_name='LINE Customer',
        price=5000,
        is_temporary=False,
        **kwargs,
    )
    schedule.set_line_user_id('U_reminder_test_001')
    schedule.save()
    return schedule


# ==============================================================
# send_day_before_reminders
# ==============================================================

@pytest.mark.django_db
class TestDayBeforeReminders:
    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_day_before_sends_reminder(self, mock_push, staff, store):
        """Sends reminder for tomorrow's schedule and sets flag."""
        now = timezone.now()
        tomorrow = (now + timedelta(days=1)).replace(
            hour=14, minute=0, second=0, microsecond=0,
        )
        schedule = _create_schedule_with_line(staff, store, tomorrow)

        from booking.services.line_reminder import send_day_before_reminders
        sent = send_day_before_reminders()

        assert sent == 1
        mock_push.assert_called_once()
        schedule.refresh_from_db()
        assert schedule.reminder_sent_day_before is True

    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_day_before_skips_already_sent(self, mock_push, staff, store):
        """Skips schedule where reminder_sent_day_before=True."""
        now = timezone.now()
        tomorrow = (now + timedelta(days=1)).replace(
            hour=14, minute=0, second=0, microsecond=0,
        )
        _create_schedule_with_line(
            staff, store, tomorrow, reminder_sent_day_before=True,
        )

        from booking.services.line_reminder import send_day_before_reminders
        sent = send_day_before_reminders()

        assert sent == 0
        mock_push.assert_not_called()

    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_day_before_skips_cancelled(self, mock_push, staff, store):
        """Skips cancelled schedules."""
        now = timezone.now()
        tomorrow = (now + timedelta(days=1)).replace(
            hour=14, minute=0, second=0, microsecond=0,
        )
        _create_schedule_with_line(
            staff, store, tomorrow, is_cancelled=True,
        )

        from booking.services.line_reminder import send_day_before_reminders
        sent = send_day_before_reminders()

        assert sent == 0
        mock_push.assert_not_called()


# ==============================================================
# send_same_day_reminders
# ==============================================================

@pytest.mark.django_db
class TestSameDayReminders:
    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_same_day_sends_reminder(self, mock_push, staff, store):
        """Sends reminder for schedule within 2 hours and sets flag."""
        now = timezone.now()
        one_hour_later = now + timedelta(hours=1)
        schedule = _create_schedule_with_line(staff, store, one_hour_later)

        from booking.services.line_reminder import send_same_day_reminders
        sent = send_same_day_reminders()

        assert sent == 1
        mock_push.assert_called_once()
        schedule.refresh_from_db()
        assert schedule.reminder_sent_same_day is True

    @patch('booking.services.line_bot_service.push_text', return_value=True)
    def test_same_day_skips_already_sent(self, mock_push, staff, store):
        """Skips schedule where reminder_sent_same_day=True."""
        now = timezone.now()
        one_hour_later = now + timedelta(hours=1)
        _create_schedule_with_line(
            staff, store, one_hour_later, reminder_sent_same_day=True,
        )

        from booking.services.line_reminder import send_same_day_reminders
        sent = send_same_day_reminders()

        assert sent == 0
        mock_push.assert_not_called()


# ==============================================================
# Celery task feature flag
# ==============================================================

@pytest.mark.django_db
class TestCeleryTaskFeatureFlag:
    def test_celery_task_checks_feature_flag(self, site_settings):
        """Task does not execute when line_reminder_enabled=False."""
        SiteSettings.objects.filter(pk=site_settings.pk).update(
            line_reminder_enabled=False,
        )

        with patch(
            'booking.services.line_reminder.send_day_before_reminders',
        ) as mock_send:
            from booking.tasks import send_day_before_reminders
            send_day_before_reminders()
            mock_send.assert_not_called()
