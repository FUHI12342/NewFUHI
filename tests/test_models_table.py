"""Tests for TableSeat and PaymentMethod models."""
import uuid
import pytest
from django.db import IntegrityError

from booking.models import TableSeat, PaymentMethod, Store


class TestTableSeatModel:
    """Tests for the TableSeat model."""

    @pytest.mark.django_db
    def test_uuid_primary_key(self, table_seat):
        """TableSeat uses UUID as primary key."""
        assert isinstance(table_seat.pk, uuid.UUID)

    @pytest.mark.django_db
    def test_unique_together_store_label(self, store):
        """TableSeat enforces unique_together on (store, label)."""
        TableSeat.objects.create(store=store, label='B1')
        with pytest.raises(IntegrityError):
            TableSeat.objects.create(store=store, label='B1')

    @pytest.mark.django_db
    def test_get_menu_url(self, table_seat, settings):
        """TableSeat.get_menu_url returns correct URL format."""
        settings.SITE_BASE_URL = 'https://example.com'
        url = table_seat.get_menu_url()
        assert url == f'https://example.com/t/{table_seat.pk}/'

    @pytest.mark.django_db
    def test_get_menu_url_no_base_url(self, table_seat, settings):
        """TableSeat.get_menu_url works when SITE_BASE_URL is not set."""
        # Remove SITE_BASE_URL if set
        if hasattr(settings, 'SITE_BASE_URL'):
            delattr(settings, 'SITE_BASE_URL')
        url = table_seat.get_menu_url()
        assert f'/t/{table_seat.pk}/' in url

    @pytest.mark.django_db
    def test_str(self, table_seat):
        """TableSeat __str__ includes store name and label."""
        result = str(table_seat)
        assert 'A1' in result
        assert table_seat.store.name in result

    @pytest.mark.django_db
    def test_is_active_default(self, store):
        """TableSeat defaults to is_active=True."""
        ts = TableSeat.objects.create(store=store, label='C1')
        assert ts.is_active is True

    @pytest.mark.django_db
    def test_auto_uuid_generation(self, store):
        """TableSeat auto-generates different UUIDs for each instance."""
        ts1 = TableSeat.objects.create(store=store, label='D1')
        ts2 = TableSeat.objects.create(store=store, label='D2')
        assert ts1.pk != ts2.pk


class TestPaymentMethodModel:
    """Tests for the PaymentMethod model."""

    @pytest.mark.django_db
    def test_method_type_choices(self, store):
        """PaymentMethod supports all method_type choices."""
        for method_type, _ in PaymentMethod.METHOD_TYPE_CHOICES:
            pm = PaymentMethod.objects.create(
                store=store,
                method_type=method_type,
                display_name=f'Test {method_type}',
            )
            assert pm.method_type == method_type
            pm.delete()  # clean up for unique_together

    @pytest.mark.django_db
    def test_unique_together_store_method_type(self, store):
        """PaymentMethod enforces unique_together on (store, method_type)."""
        PaymentMethod.objects.create(
            store=store, method_type='cash', display_name='Cash',
        )
        with pytest.raises(IntegrityError):
            PaymentMethod.objects.create(
                store=store, method_type='cash', display_name='Cash 2',
            )

    @pytest.mark.django_db
    def test_str(self, store):
        """PaymentMethod __str__ includes store name and display name."""
        pm = PaymentMethod.objects.create(
            store=store, method_type='paypay', display_name='PayPay',
        )
        result = str(pm)
        assert 'PayPay' in result
        assert store.name in result
