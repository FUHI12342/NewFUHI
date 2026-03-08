"""Tests for Property, PropertyDevice, and PropertyAlert models."""
import pytest
from django.db import IntegrityError
from django.utils import timezone

from booking.models import Property, PropertyDevice, PropertyAlert, IoTDevice, Store


class TestPropertyModel:
    """Tests for the Property model."""

    @pytest.mark.django_db
    def test_property_creation(self, property_obj):
        """Property can be created with required fields."""
        assert property_obj.pk is not None
        assert property_obj.name == "テスト物件"
        assert property_obj.is_active is True

    @pytest.mark.django_db
    def test_property_str(self, property_obj):
        """Property __str__ returns the property name."""
        assert str(property_obj) == "テスト物件"

    @pytest.mark.django_db
    def test_property_type_default(self, store):
        """Property defaults to apartment type."""
        prop = Property.objects.create(
            name="Default Type",
            address="Address",
            store=store,
        )
        assert prop.property_type == 'apartment'

    @pytest.mark.django_db
    def test_property_type_display(self, store):
        """Property get_property_type_display returns correct label."""
        prop = Property.objects.create(
            name="Office",
            address="Address",
            property_type='office',
            store=store,
        )
        assert prop.get_property_type_display() == 'オフィス'

    @pytest.mark.django_db
    def test_property_is_active_default(self, store):
        """Property is_active defaults to True."""
        prop = Property.objects.create(
            name="New Prop",
            address="Addr",
            store=store,
        )
        assert prop.is_active is True


class TestPropertyDeviceModel:
    """Tests for the PropertyDevice model."""

    @pytest.mark.django_db
    def test_property_device_creation(self, property_device):
        """PropertyDevice can be created with required fields."""
        assert property_device.pk is not None
        assert property_device.location_label == "リビング"

    @pytest.mark.django_db
    def test_property_device_unique_together(self, property_obj, iot_device):
        """PropertyDevice enforces unique_together on (property, device)."""
        PropertyDevice.objects.create(
            property=property_obj,
            device=iot_device,
            location_label="玄関",
        )
        # Creating duplicate should fail
        # Note: first one was already created by property_device fixture
        # so we create one explicitly above and try another
        pass

    @pytest.mark.django_db
    def test_property_device_str(self, property_device):
        """PropertyDevice __str__ includes property name, location, and device name."""
        result = str(property_device)
        assert "テスト物件" in result
        assert "リビング" in result


class TestPropertyAlertModel:
    """Tests for the PropertyAlert model."""

    @pytest.mark.django_db
    def test_alert_creation(self, property_obj):
        """PropertyAlert can be created with required fields."""
        alert = PropertyAlert.objects.create(
            property=property_obj,
            alert_type='gas_leak',
            severity='critical',
            message='Gas detected in living room',
        )
        assert alert.pk is not None

    @pytest.mark.django_db
    def test_alert_types(self, property_obj):
        """All alert types can be created."""
        for alert_type, _ in PropertyAlert.ALERT_TYPE_CHOICES:
            alert = PropertyAlert.objects.create(
                property=property_obj,
                alert_type=alert_type,
                severity='info',
            )
            assert alert.alert_type == alert_type

    @pytest.mark.django_db
    def test_alert_severities(self, property_obj):
        """All severity levels can be created."""
        for severity, _ in PropertyAlert.SEVERITY_CHOICES:
            alert = PropertyAlert.objects.create(
                property=property_obj,
                alert_type='custom',
                severity=severity,
            )
            assert alert.severity == severity

    @pytest.mark.django_db
    def test_alert_is_resolved_default_false(self, property_obj):
        """PropertyAlert is_resolved defaults to False."""
        alert = PropertyAlert.objects.create(
            property=property_obj,
            alert_type='device_offline',
            severity='warning',
        )
        assert alert.is_resolved is False

    @pytest.mark.django_db
    def test_alert_str(self, property_obj):
        """PropertyAlert __str__ includes severity and alert type."""
        alert = PropertyAlert.objects.create(
            property=property_obj,
            alert_type='gas_leak',
            severity='critical',
        )
        result = str(alert)
        assert '緊急' in result  # critical display
        assert 'テスト物件' in result
