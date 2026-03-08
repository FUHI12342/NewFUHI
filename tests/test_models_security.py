"""Tests for SecurityAudit, SecurityLog, and CostReport models."""
import uuid
import pytest
from decimal import Decimal

from booking.models import SecurityAudit, SecurityLog, CostReport


class TestSecurityAuditModel:
    """Tests for the SecurityAudit model."""

    @pytest.mark.django_db
    def test_creation_with_all_fields(self):
        """SecurityAudit can be created with all required fields."""
        audit = SecurityAudit.objects.create(
            run_id=uuid.uuid4(),
            check_name='debug_mode_check',
            category='django_settings',
            severity='critical',
            status='fail',
            message='DEBUG is True in production',
            recommendation='Set DEBUG=False',
        )
        assert audit.pk is not None
        assert audit.check_name == 'debug_mode_check'

    @pytest.mark.django_db
    def test_str_format(self):
        """SecurityAudit __str__ includes severity display and check name."""
        audit = SecurityAudit.objects.create(
            check_name='secret_key_check',
            category='credentials',
            severity='high',
            status='pass',
            message='Secret key is properly set',
        )
        result = str(audit)
        assert '高' in result  # high severity display
        assert 'secret_key_check' in result
        assert '合格' in result  # pass status display

    @pytest.mark.django_db
    def test_severity_choices(self):
        """All severity choices are valid."""
        for severity, _ in SecurityAudit.SEVERITY_CHOICES:
            audit = SecurityAudit.objects.create(
                check_name=f'test_{severity}',
                category='django_settings',
                severity=severity,
                status='pass',
                message='test',
            )
            assert audit.severity == severity

    @pytest.mark.django_db
    def test_status_choices(self):
        """All status choices are valid."""
        for status, _ in SecurityAudit.STATUS_CHOICES:
            audit = SecurityAudit.objects.create(
                check_name=f'test_{status}',
                category='django_settings',
                severity='info',
                status=status,
                message='test',
            )
            assert audit.status == status

    @pytest.mark.django_db
    def test_category_choices(self):
        """All category choices are valid."""
        for category, _ in SecurityAudit.CATEGORY_CHOICES:
            audit = SecurityAudit.objects.create(
                check_name=f'test_{category}',
                category=category,
                severity='info',
                status='pass',
                message='test',
            )
            assert audit.category == category


class TestSecurityLogModel:
    """Tests for the SecurityLog model."""

    @pytest.mark.django_db
    def test_event_type_choices(self):
        """All event_type choices are valid."""
        for event_type, _ in SecurityLog.EVENT_TYPE_CHOICES:
            log = SecurityLog.objects.create(
                event_type=event_type,
                severity='info',
                ip_address='127.0.0.1',
            )
            assert log.event_type == event_type

    @pytest.mark.django_db
    def test_severity_choices(self):
        """All severity choices are valid."""
        for severity, _ in SecurityLog.SEVERITY_CHOICES:
            log = SecurityLog.objects.create(
                event_type='login_success',
                severity=severity,
                ip_address='127.0.0.1',
            )
            assert log.severity == severity

    @pytest.mark.django_db
    def test_str(self):
        """SecurityLog __str__ includes severity, event type, username and IP."""
        log = SecurityLog.objects.create(
            event_type='login_fail',
            severity='warning',
            username='testuser',
            ip_address='192.168.1.1',
        )
        result = str(log)
        assert '警告' in result
        assert 'testuser' in result
        assert '192.168.1.1' in result


class TestCostReportModel:
    """Tests for the CostReport model."""

    @pytest.mark.django_db
    def test_status_choices(self):
        """All status choices are valid."""
        for status, _ in CostReport.STATUS_CHOICES:
            report = CostReport.objects.create(
                check_name=f'test_{status}',
                resource_type='total',
                status=status,
            )
            assert report.status == status

    @pytest.mark.django_db
    def test_resource_type_choices(self):
        """All resource_type choices are valid."""
        for rt, _ in CostReport.RESOURCE_TYPE_CHOICES:
            report = CostReport.objects.create(
                check_name=f'test_{rt}',
                resource_type=rt,
                status='ok',
            )
            assert report.resource_type == rt

    @pytest.mark.django_db
    def test_str(self):
        """CostReport __str__ includes status display, check name, resource type."""
        report = CostReport.objects.create(
            check_name='ec2_instances',
            resource_type='ec2',
            status='warn',
            estimated_monthly_cost=Decimal('50.00'),
        )
        result = str(report)
        assert '警告' in result
        assert 'ec2_instances' in result

    @pytest.mark.django_db
    def test_default_cost(self):
        """CostReport estimated_monthly_cost defaults to 0."""
        report = CostReport.objects.create(
            check_name='test_default',
            resource_type='total',
            status='ok',
        )
        assert report.estimated_monthly_cost == Decimal('0')
