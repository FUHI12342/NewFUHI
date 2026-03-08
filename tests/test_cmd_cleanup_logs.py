"""Tests for cleanup_security_logs management command."""
import pytest
from datetime import timedelta
from django.core.management import call_command
from django.utils import timezone

from booking.models import SecurityLog


class TestCleanupSecurityLogsCommand:
    """Tests for the cleanup_security_logs management command."""

    @pytest.mark.django_db
    def test_deletes_old_logs(self):
        """Command deletes logs older than specified days."""
        old_log = SecurityLog.objects.create(
            event_type='login_success',
            severity='info',
            ip_address='127.0.0.1',
        )
        # Manually backdate created_at
        SecurityLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(days=100),
        )
        call_command('cleanup_security_logs', '--days', '90')
        assert not SecurityLog.objects.filter(pk=old_log.pk).exists()

    @pytest.mark.django_db
    def test_keeps_recent_logs(self):
        """Command keeps logs newer than specified days."""
        recent_log = SecurityLog.objects.create(
            event_type='login_fail',
            severity='warning',
            ip_address='127.0.0.1',
        )
        call_command('cleanup_security_logs', '--days', '90')
        assert SecurityLog.objects.filter(pk=recent_log.pk).exists()

    @pytest.mark.django_db
    def test_default_90_days(self):
        """Command uses default 90 days when --days is not specified."""
        old_log = SecurityLog.objects.create(
            event_type='api_auth_fail',
            severity='warning',
            ip_address='10.0.0.1',
        )
        SecurityLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(days=91),
        )
        call_command('cleanup_security_logs')
        assert not SecurityLog.objects.filter(pk=old_log.pk).exists()

    @pytest.mark.django_db
    def test_keeps_logs_within_default_period(self):
        """Command with default 90 days keeps logs within period."""
        log_89_days = SecurityLog.objects.create(
            event_type='login_success',
            severity='info',
            ip_address='10.0.0.1',
        )
        SecurityLog.objects.filter(pk=log_89_days.pk).update(
            created_at=timezone.now() - timedelta(days=89),
        )
        call_command('cleanup_security_logs')
        assert SecurityLog.objects.filter(pk=log_89_days.pk).exists()

    @pytest.mark.django_db
    def test_custom_days_parameter(self):
        """Command respects custom --days parameter."""
        log = SecurityLog.objects.create(
            event_type='suspicious_request',
            severity='critical',
            ip_address='192.168.1.1',
        )
        SecurityLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(days=35),
        )
        call_command('cleanup_security_logs', '--days', '30')
        assert not SecurityLog.objects.filter(pk=log.pk).exists()
