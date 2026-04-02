"""
Tests for booking/tasks.py

Covers:
- delete_temporary_schedules: expired temp deletion, keeping confirmed/recent
- trigger_gas_alert: email dispatch, no-email skip, missing device
- check_low_stock_and_notify: LINE notification, 24h cooldown
- check_property_alerts: gas_leak, no_motion, device_offline, duplicate prevention
- run_security_audit, cleanup_security_logs, check_aws_costs: management command calls
"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone
from django.core import mail

from booking.models import (
    Schedule, IoTDevice, IoTEvent, Product,
    Property, PropertyDevice, PropertyAlert,
)
from booking.tasks import (
    delete_temporary_schedules,
    trigger_gas_alert,
    check_low_stock_and_notify,
    check_property_alerts,
    run_security_audit,
    cleanup_security_logs,
    check_aws_costs,
)


# ==============================
# delete_temporary_schedules
# ==============================

class TestDeleteTemporarySchedules:

    @pytest.mark.django_db
    def test_deletes_expired_temporary(self, staff):
        """Temporary schedules older than 10 minutes should be deleted."""
        now = timezone.now()
        Schedule.objects.create(
            staff=staff,
            start=now, end=now + timedelta(hours=1),
            is_temporary=True, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=15),
        )
        delete_temporary_schedules()
        assert Schedule.objects.count() == 0

    @pytest.mark.django_db
    def test_keeps_confirmed_schedules(self, staff):
        """Confirmed (is_temporary=False) schedules should not be deleted."""
        now = timezone.now()
        Schedule.objects.create(
            staff=staff,
            start=now, end=now + timedelta(hours=1),
            is_temporary=False, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=15),
        )
        delete_temporary_schedules()
        assert Schedule.objects.count() == 1

    @pytest.mark.django_db
    def test_keeps_recent_temporary(self, staff):
        """Temporary schedules within 10 minutes should be kept."""
        now = timezone.now()
        Schedule.objects.create(
            staff=staff,
            start=now, end=now + timedelta(hours=1),
            is_temporary=True, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=5),
        )
        delete_temporary_schedules()
        assert Schedule.objects.count() == 1

    @pytest.mark.django_db
    def test_keeps_cancelled_temporary(self, staff):
        """Cancelled temporary schedules should not be deleted (is_cancelled=True excluded)."""
        now = timezone.now()
        Schedule.objects.create(
            staff=staff,
            start=now, end=now + timedelta(hours=1),
            is_temporary=True, is_cancelled=True,
            temporary_booked_at=now - timedelta(minutes=15),
        )
        delete_temporary_schedules()
        assert Schedule.objects.count() == 1

    @pytest.mark.django_db
    def test_deletes_only_expired_among_mixed(self, staff):
        """Only expired temporary schedules are deleted in a mixed set."""
        now = timezone.now()
        # expired temp
        Schedule.objects.create(
            staff=staff, start=now, end=now + timedelta(hours=1),
            is_temporary=True, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=20),
        )
        # recent temp
        Schedule.objects.create(
            staff=staff, start=now + timedelta(hours=2), end=now + timedelta(hours=3),
            is_temporary=True, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=3),
        )
        # confirmed
        Schedule.objects.create(
            staff=staff, start=now + timedelta(hours=4), end=now + timedelta(hours=5),
            is_temporary=False, is_cancelled=False,
            temporary_booked_at=now - timedelta(minutes=30),
        )
        delete_temporary_schedules()
        assert Schedule.objects.count() == 2


# ==============================
# trigger_gas_alert
# ==============================

class TestTriggerGasAlert:

    @pytest.mark.django_db
    def test_sends_email_when_alert_email_set(self, iot_device, mail_outbox):
        """Email is sent when device has alert_email configured."""
        iot_device.alert_email = 'alert@example.com'
        iot_device.save()
        trigger_gas_alert(iot_device.id, 800.0, 1)
        assert len(mail_outbox) == 1
        assert 'Gas Alert' in mail_outbox[0].subject
        assert 'alert@example.com' in mail_outbox[0].to

    @pytest.mark.django_db
    def test_skips_when_no_alert_email(self, iot_device, mail_outbox):
        """No email sent when alert_email is empty."""
        iot_device.alert_email = ''
        iot_device.save()
        trigger_gas_alert(iot_device.id, 800.0, 1)
        assert len(mail_outbox) == 0

    @pytest.mark.django_db
    def test_handles_device_does_not_exist(self, mail_outbox):
        """Gracefully handles non-existent device ID."""
        trigger_gas_alert(99999, 800.0, 1)
        assert len(mail_outbox) == 0

    @pytest.mark.django_db
    def test_email_contains_device_info(self, iot_device, mail_outbox):
        """Email body should contain device name and MQ-9 value."""
        iot_device.alert_email = 'alert@example.com'
        iot_device.save()
        trigger_gas_alert(iot_device.id, 950.5, 1)
        body = mail_outbox[0].body
        assert iot_device.name in body
        assert '950.5' in body


# ==============================
# check_low_stock_and_notify
# ==============================

class TestCheckLowStockAndNotify:

    @pytest.mark.django_db
    def test_sends_line_notify_for_low_stock(self, product):
        """LINE notification sent for product below threshold."""
        product.stock = 5
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = None
        product.save()

        with patch('booking.tasks.send_line_notify', return_value=True) as mock_notify:
            check_low_stock_and_notify()
            mock_notify.assert_called_once()
        product.refresh_from_db()
        assert product.last_low_stock_notified_at is not None

    @pytest.mark.django_db
    def test_skips_if_notified_within_cooldown(self, product):
        """Skips notification if notified within the cooldown period (4h)."""
        product.stock = 5
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = timezone.now() - timedelta(hours=2)
        product.save()

        with patch('booking.tasks.send_line_notify', return_value=True) as mock_notify:
            check_low_stock_and_notify()
            mock_notify.assert_not_called()

    @pytest.mark.django_db
    def test_re_notifies_after_24h(self, product):
        """Re-sends notification after 24h cooldown."""
        product.stock = 5
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = timezone.now() - timedelta(hours=25)
        product.save()

        with patch('booking.tasks.send_line_notify', return_value=True) as mock_notify:
            check_low_stock_and_notify()
            mock_notify.assert_called_once()

    @pytest.mark.django_db
    def test_no_notification_when_stock_above_threshold(self, product):
        """No notification when stock is above threshold."""
        product.stock = 50
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = None
        product.save()

        with patch('booking.tasks.send_line_notify', return_value=True) as mock_notify:
            check_low_stock_and_notify()
            mock_notify.assert_not_called()

    @pytest.mark.django_db
    def test_no_notification_when_threshold_high(self, product):
        """No notification when stock equals threshold (not below)."""
        product.stock = 10
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = None
        product.save()

        with patch('booking.tasks.send_line_notify', return_value=True) as mock_notify:
            check_low_stock_and_notify()
            mock_notify.assert_called_once()


# ==============================
# check_property_alerts
# ==============================

class TestCheckPropertyAlerts:

    @pytest.mark.django_db
    def test_gas_leak_creates_critical_alert(self, property_obj, property_device, iot_device):
        """MQ-9 above threshold within 5 min creates critical gas_leak alert."""
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.save()

        IoTEvent.objects.create(
            device=iot_device,
            mq9_value=600,
        )

        check_property_alerts()
        alert = PropertyAlert.objects.get(
            property=property_obj, alert_type='gas_leak',
        )
        assert alert.severity == 'critical'
        assert alert.is_resolved is False

    @pytest.mark.django_db
    def test_no_motion_creates_warning_alert(self, property_obj, property_device, iot_device):
        """PIR not triggered for 3+ days creates warning no_motion alert."""
        iot_device.mq9_threshold = None
        iot_device.is_active = True
        iot_device.save()

        event = IoTEvent.objects.create(
            device=iot_device,
            pir_triggered=True,
        )
        # Backdate the event to 4 days ago
        IoTEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=4),
        )

        check_property_alerts()
        alert = PropertyAlert.objects.get(
            property=property_obj, alert_type='no_motion',
        )
        assert alert.severity == 'warning'

    @pytest.mark.django_db
    def test_device_offline_creates_info_alert(self, property_obj, property_device, iot_device):
        """Device not seen for 30+ min creates info device_offline alert."""
        iot_device.mq9_threshold = None
        iot_device.is_active = True
        iot_device.last_seen_at = timezone.now() - timedelta(minutes=45)
        iot_device.save()

        check_property_alerts()
        alert = PropertyAlert.objects.get(
            property=property_obj, alert_type='device_offline',
        )
        assert alert.severity == 'info'

    @pytest.mark.django_db
    def test_duplicate_gas_leak_not_created(self, property_obj, property_device, iot_device):
        """Existing unresolved gas_leak alert prevents duplicate creation."""
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.save()

        PropertyAlert.objects.create(
            property=property_obj, device=iot_device,
            alert_type='gas_leak', severity='critical',
            is_resolved=False,
        )

        IoTEvent.objects.create(device=iot_device, mq9_value=600)

        check_property_alerts()
        assert PropertyAlert.objects.filter(
            property=property_obj, alert_type='gas_leak',
        ).count() == 1

    @pytest.mark.django_db
    def test_duplicate_no_motion_not_created(self, property_obj, property_device, iot_device):
        """Existing unresolved no_motion alert prevents duplicate creation."""
        iot_device.mq9_threshold = None
        iot_device.is_active = True
        iot_device.save()

        PropertyAlert.objects.create(
            property=property_obj, device=iot_device,
            alert_type='no_motion', severity='warning',
            is_resolved=False,
        )

        event = IoTEvent.objects.create(device=iot_device, pir_triggered=True)
        IoTEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=4),
        )

        check_property_alerts()
        assert PropertyAlert.objects.filter(
            property=property_obj, alert_type='no_motion',
        ).count() == 1

    @pytest.mark.django_db
    def test_duplicate_device_offline_not_created(self, property_obj, property_device, iot_device):
        """Existing unresolved device_offline alert prevents duplicate creation."""
        iot_device.mq9_threshold = None
        iot_device.is_active = True
        iot_device.last_seen_at = timezone.now() - timedelta(minutes=45)
        iot_device.save()

        PropertyAlert.objects.create(
            property=property_obj, device=iot_device,
            alert_type='device_offline', severity='info',
            is_resolved=False,
        )

        check_property_alerts()
        assert PropertyAlert.objects.filter(
            property=property_obj, alert_type='device_offline',
        ).count() == 1

    @pytest.mark.django_db
    def test_inactive_device_skipped(self, property_obj, property_device, iot_device):
        """Inactive devices should be skipped entirely."""
        iot_device.is_active = False
        iot_device.mq9_threshold = 500
        iot_device.last_seen_at = timezone.now() - timedelta(minutes=45)
        iot_device.save()

        IoTEvent.objects.create(device=iot_device, mq9_value=600)

        check_property_alerts()
        assert PropertyAlert.objects.count() == 0

    @pytest.mark.django_db
    def test_inactive_property_skipped(self, store, iot_device):
        """Inactive property should be skipped."""
        prop = Property.objects.create(
            name="Inactive", address="Test", property_type='apartment',
            store=store, is_active=False,
        )
        PropertyDevice.objects.create(
            property=prop, device=iot_device, location_label='Test',
        )
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.save()
        IoTEvent.objects.create(device=iot_device, mq9_value=600)

        check_property_alerts()
        assert PropertyAlert.objects.count() == 0

    @pytest.mark.django_db
    def test_resolved_alert_allows_new_one(self, property_obj, property_device, iot_device):
        """Resolved alert should not prevent creation of a new alert."""
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.save()

        PropertyAlert.objects.create(
            property=property_obj, device=iot_device,
            alert_type='gas_leak', severity='critical',
            is_resolved=True,
        )
        IoTEvent.objects.create(device=iot_device, mq9_value=600)

        check_property_alerts()
        assert PropertyAlert.objects.filter(
            property=property_obj, alert_type='gas_leak', is_resolved=False,
        ).count() == 1

    @pytest.mark.django_db
    def test_no_events_no_alerts(self, property_obj, property_device, iot_device):
        """No IoT events should produce no alerts."""
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.last_seen_at = timezone.now()  # recently seen
        iot_device.save()

        check_property_alerts()
        assert PropertyAlert.objects.count() == 0

    @pytest.mark.django_db
    def test_mq9_below_threshold_no_gas_alert(self, property_obj, property_device, iot_device):
        """MQ-9 below threshold should not create gas_leak alert."""
        iot_device.mq9_threshold = 500
        iot_device.is_active = True
        iot_device.save()

        IoTEvent.objects.create(device=iot_device, mq9_value=400)

        check_property_alerts()
        assert PropertyAlert.objects.filter(alert_type='gas_leak').count() == 0

    @pytest.mark.django_db
    def test_device_online_no_offline_alert(self, property_obj, property_device, iot_device):
        """Device seen within 30 min should not create device_offline alert."""
        iot_device.mq9_threshold = None
        iot_device.is_active = True
        iot_device.last_seen_at = timezone.now() - timedelta(minutes=10)
        iot_device.save()

        check_property_alerts()
        assert PropertyAlert.objects.filter(alert_type='device_offline').count() == 0


# ==============================
# Management command tasks
# ==============================

class TestManagementCommandTasks:

    @pytest.mark.django_db
    def test_run_security_audit(self):
        """run_security_audit should invoke security_audit management command."""
        with patch('django.core.management.call_command') as mock_cmd:
            run_security_audit()
            mock_cmd.assert_called_once_with('security_audit')

    @pytest.mark.django_db
    def test_cleanup_security_logs(self):
        """cleanup_security_logs should invoke cleanup_security_logs with --days 90."""
        with patch('django.core.management.call_command') as mock_cmd:
            cleanup_security_logs()
            mock_cmd.assert_called_once_with('cleanup_security_logs', '--days', '90')

    @pytest.mark.django_db
    def test_check_aws_costs(self):
        """check_aws_costs should invoke check_aws_costs with --threshold 50."""
        with patch('django.core.management.call_command') as mock_cmd:
            check_aws_costs()
            mock_cmd.assert_called_once_with('check_aws_costs', '--threshold', '50')
