"""
Tests for booking/models.py -- Order, OrderItem, StockMovement, apply_stock_movement

Covers:
- apply_stock_movement: IN/OUT/ADJUST types, negative stock handling, threshold notification reset
- Product properties: is_sold_out, should_notify_low_stock
- OrderItem status choices
- Basic model creation
"""
import pytest
from django.utils import timezone

from booking.models import (
    Product, Order, OrderItem, StockMovement, apply_stock_movement,
    Store, Category,
)


# ==============================
# apply_stock_movement
# ==============================

class TestApplyStockMovement:

    @pytest.mark.django_db
    def test_type_in_increases_stock(self, product):
        """TYPE_IN: stock increases by abs(qty)."""
        initial = product.stock  # 100
        apply_stock_movement(product, StockMovement.TYPE_IN, 20)
        assert product.stock == initial + 20

    @pytest.mark.django_db
    def test_type_out_decreases_stock(self, product):
        """TYPE_OUT: stock decreases by abs(qty)."""
        initial = product.stock  # 100
        apply_stock_movement(product, StockMovement.TYPE_OUT, 30)
        assert product.stock == initial - 30

    @pytest.mark.django_db
    def test_type_adjust_positive(self, product):
        """TYPE_ADJUST with positive qty adds to stock."""
        initial = product.stock
        apply_stock_movement(product, StockMovement.TYPE_ADJUST, 15)
        assert product.stock == initial + 15

    @pytest.mark.django_db
    def test_type_adjust_negative(self, product):
        """TYPE_ADJUST with negative qty reduces stock."""
        initial = product.stock
        apply_stock_movement(product, StockMovement.TYPE_ADJUST, -10)
        assert product.stock == initial - 10

    @pytest.mark.django_db
    def test_negative_stock_raises_value_error(self, product):
        """Negative stock raises ValueError when allow_negative=False."""
        with pytest.raises(ValueError, match="stock would become negative"):
            apply_stock_movement(product, StockMovement.TYPE_OUT, 200)

    @pytest.mark.django_db
    def test_allow_negative_permits_negative_stock(self, product):
        """allow_negative=True allows stock to go below zero."""
        apply_stock_movement(product, StockMovement.TYPE_OUT, 200, allow_negative=True)
        assert product.stock < 0

    @pytest.mark.django_db
    def test_low_stock_notification_reset(self, product):
        """When stock goes above threshold, last_low_stock_notified_at is reset to None."""
        # Set up: product below threshold with notification timestamp
        product.stock = 5
        product.last_low_stock_notified_at = timezone.now()
        product.save()

        # Bring stock above threshold (threshold=10)
        apply_stock_movement(product, StockMovement.TYPE_IN, 20)
        # stock = 5 + 20 = 25 > threshold 10 => reset notification
        assert product.last_low_stock_notified_at is None

    @pytest.mark.django_db
    def test_invalid_movement_type_raises(self, product):
        """Invalid movement_type raises ValueError."""
        with pytest.raises(ValueError, match="invalid movement_type"):
            apply_stock_movement(product, 'INVALID', 10)

    @pytest.mark.django_db
    def test_type_in_uses_absolute_value(self, product):
        """TYPE_IN uses abs(qty) even if negative qty is passed."""
        initial = product.stock
        apply_stock_movement(product, StockMovement.TYPE_IN, -10)
        assert product.stock == initial + 10

    @pytest.mark.django_db
    def test_type_out_uses_absolute_value(self, product):
        """TYPE_OUT uses abs(qty) even if negative qty is passed."""
        initial = product.stock
        apply_stock_movement(product, StockMovement.TYPE_OUT, -10)
        assert product.stock == initial - 10


# ==============================
# Product properties
# ==============================

class TestProductProperties:

    @pytest.mark.django_db
    def test_is_sold_out_when_zero(self, product):
        """Product.is_sold_out returns True when stock <= 0."""
        product.stock = 0
        product.save()
        assert product.is_sold_out is True

    @pytest.mark.django_db
    def test_is_sold_out_when_positive(self, product):
        """Product.is_sold_out returns False when stock > 0."""
        assert product.stock > 0
        assert product.is_sold_out is False

    @pytest.mark.django_db
    def test_should_notify_low_stock_true(self, product):
        """should_notify_low_stock returns True when stock<=threshold and never notified."""
        product.stock = 5
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = None
        product.save()
        assert product.should_notify_low_stock() is True

    @pytest.mark.django_db
    def test_should_notify_low_stock_false_already_notified(self, product):
        """should_notify_low_stock returns False when already notified."""
        product.stock = 5
        product.low_stock_threshold = 10
        product.last_low_stock_notified_at = timezone.now()
        product.save()
        assert product.should_notify_low_stock() is False


# ==============================
# OrderItem status choices
# ==============================

class TestOrderItemStatusChoices:

    def test_status_ordered_exists(self):
        assert OrderItem.STATUS_ORDERED == 'ORDERED'

    def test_status_preparing_exists(self):
        assert OrderItem.STATUS_PREPARING == 'PREPARING'

    def test_status_served_exists(self):
        assert OrderItem.STATUS_SERVED == 'SERVED'

    def test_status_closed_exists(self):
        assert OrderItem.STATUS_CLOSED == 'CLOSED'

    def test_status_choices_has_four_entries(self):
        assert len(OrderItem.STATUS_CHOICES) == 4


# ==============================
# Basic model creation
# ==============================

class TestModelCreation:

    @pytest.mark.django_db
    def test_order_creation(self, store):
        """Order can be created with store and status."""
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN)
        assert order.pk is not None
        assert order.status == Order.STATUS_OPEN

    @pytest.mark.django_db
    def test_order_item_creation(self, order, product):
        """OrderItem can be created with order, product, qty, unit_price."""
        item = OrderItem.objects.create(
            order=order, product=product, qty=3,
            unit_price=500, status=OrderItem.STATUS_ORDERED,
        )
        assert item.pk is not None
        assert item.qty == 3
        assert item.unit_price == 500

    @pytest.mark.django_db
    def test_stock_movement_creation(self, store, product, staff):
        """StockMovement can be created."""
        sm = StockMovement.objects.create(
            store=store, product=product,
            movement_type=StockMovement.TYPE_IN,
            qty=50, by_staff=staff, note='test movement',
        )
        assert sm.pk is not None
        assert sm.movement_type == StockMovement.TYPE_IN
