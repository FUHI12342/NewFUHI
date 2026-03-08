"""Tests for cancel_expired_temp_bookings management command."""
import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone

from booking.models import Schedule, Staff


class TestCancelExpiredTempBookingsCommand:
    """Tests for the cancel_expired_temp_bookings command."""

    @pytest.mark.django_db
    def test_cancels_expired_temp_bookings(self, staff):
        """Command cancels temp bookings older than 15 minutes."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now - timedelta(minutes=20),
            end=now - timedelta(minutes=10),
            is_temporary=True,
            is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=20),
        )
        call_command('cancel_expired_temp_bookings')
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True

    @pytest.mark.django_db
    def test_keeps_recent_temp_bookings(self, staff):
        """Command keeps temp bookings created within 15 minutes."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now + timedelta(hours=1),
            end=now + timedelta(hours=2),
            is_temporary=True,
            is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=5),
        )
        call_command('cancel_expired_temp_bookings')
        schedule.refresh_from_db()
        assert schedule.is_cancelled is False

    @pytest.mark.django_db
    def test_keeps_confirmed_bookings(self, staff):
        """Command does not cancel confirmed (non-temporary) bookings."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now - timedelta(minutes=30),
            end=now - timedelta(minutes=20),
            is_temporary=False,
            is_cancelled=False,
        )
        call_command('cancel_expired_temp_bookings')
        schedule.refresh_from_db()
        assert schedule.is_cancelled is False

    @pytest.mark.django_db
    def test_keeps_already_cancelled(self, staff):
        """Command does not re-process already cancelled bookings."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now - timedelta(minutes=30),
            end=now - timedelta(minutes=20),
            is_temporary=True,
            is_cancelled=True,
            temporary_booked_at=now - timedelta(minutes=30),
        )
        call_command('cancel_expired_temp_bookings')
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True

    @pytest.mark.django_db
    def test_uses_start_when_temporary_booked_at_null(self, staff):
        """Command uses start time when temporary_booked_at is null."""
        now = timezone.now()
        schedule = Schedule.objects.create(
            staff=staff,
            start=now - timedelta(minutes=20),
            end=now - timedelta(minutes=10),
            is_temporary=True,
            is_cancelled=False,
            temporary_booked_at=None,
        )
        call_command('cancel_expired_temp_bookings')
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True
