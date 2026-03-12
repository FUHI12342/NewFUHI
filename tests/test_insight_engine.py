"""Tests for booking.services.insight_engine."""
import pytest
from datetime import timedelta
from django.utils import timezone

from django.contrib.auth.models import User

from booking.models import (
    Store, Staff, Product, Category, Order, OrderItem,
    Schedule, ShiftPeriod, ShiftAssignment, BusinessInsight,
)
from booking.services.insight_engine import generate_insights


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


@pytest.fixture
def store(db):
    return Store.objects.create(name='TestInsightStore')


@pytest.fixture
def category(store):
    return Category.objects.create(name='TestCat', store=store)


def _create_order_at(store, days_ago):
    """Create order and backdate via queryset update (auto_now_add bypass)."""
    order = Order.objects.create(store=store)
    ts = timezone.now() - timedelta(days=days_ago)
    Order.objects.filter(pk=order.pk).update(created_at=ts)
    order.refresh_from_db()
    return order


class TestGenerateInsights:
    """Test the main generate_insights entry point."""

    @pytest.mark.django_db
    def test_no_data_no_crash(self, store):
        result = generate_insights(store=store)
        assert isinstance(result, list)

    @pytest.mark.django_db
    def test_returns_list(self, store):
        result = generate_insights(store=store)
        assert isinstance(result, list)

    @pytest.mark.django_db
    def test_all_stores(self, store):
        result = generate_insights(store=None)
        assert isinstance(result, list)


class TestSalesDrop:
    """Test _check_sales_drop detection."""

    @pytest.mark.django_db
    def test_detects_sales_drop(self, store, category):
        """High baseline + low recent → should detect drop."""
        for week in range(4):
            day_offset = 10 + (week * 7)
            order = _create_order_at(store, day_offset)
            prod = Product.objects.create(
                name=f'P-baseline-{week}', sku=f'BL-{week}',
                store=store, category=category,
                price=1000, stock=100, low_stock_threshold=5,
            )
            OrderItem.objects.create(
                order=order, product=prod, qty=10, unit_price=1000,
            )

        recent_order = _create_order_at(store, 1)
        recent_prod = Product.objects.create(
            name='P-recent', sku='RC-1', store=store, category=category,
            price=100, stock=100, low_stock_threshold=5,
        )
        OrderItem.objects.create(
            order=recent_order, product=recent_prod, qty=1, unit_price=100,
        )

        insights = generate_insights(store=store)
        sales_insights = [i for i in insights if i.category == 'sales']
        assert len(sales_insights) >= 1
        assert '減少' in sales_insights[0].title

    @pytest.mark.django_db
    def test_no_drop_when_stable(self, store, category):
        """Same revenue recent vs baseline → no drop."""
        prod = Product.objects.create(
            name='Stable', sku='STABLE-1', store=store, category=category,
            price=1000, stock=100, low_stock_threshold=5,
        )
        for day_offset in [3, 10, 17, 24, 31]:
            order = _create_order_at(store, day_offset)
            OrderItem.objects.create(
                order=order, product=prod, qty=10, unit_price=1000,
            )
        insights = generate_insights(store=store)
        sales_insights = [i for i in insights if i.category == 'sales']
        assert len(sales_insights) == 0


class TestLowStock:
    """Test _check_low_stock detection."""

    @pytest.mark.django_db
    def test_detects_low_stock(self, store, category):
        Product.objects.create(
            name='LowItem', sku='LOW-1', store=store, category=category,
            price=500, stock=2, low_stock_threshold=10, is_active=True,
        )
        insights = generate_insights(store=store)
        inv_insights = [i for i in insights if i.category == 'inventory']
        assert len(inv_insights) >= 1
        assert 'LowItem' in inv_insights[0].title

    @pytest.mark.django_db
    def test_detects_out_of_stock(self, store, category):
        Product.objects.create(
            name='OutItem', sku='OUT-1', store=store, category=category,
            price=500, stock=0, low_stock_threshold=10, is_active=True,
        )
        insights = generate_insights(store=store)
        inv_insights = [i for i in insights if i.category == 'inventory']
        assert len(inv_insights) >= 1
        assert inv_insights[0].severity == 'critical'

    @pytest.mark.django_db
    def test_no_alert_when_stocked(self, store, category):
        Product.objects.create(
            name='WellStocked', sku='WELL-1', store=store, category=category,
            price=500, stock=100, low_stock_threshold=10, is_active=True,
        )
        insights = generate_insights(store=store)
        inv_insights = [i for i in insights if i.category == 'inventory']
        assert len(inv_insights) == 0


class TestCancellations:
    """Test _check_reservation_cancellations."""

    @pytest.mark.django_db
    def test_detects_high_cancellation(self, store):
        user = User.objects.create_user(username='cancel_staff', password='pass')
        staff = Staff.objects.create(name='CancelTestStaff', store=store, user=user)
        now = timezone.now()
        for i in range(10):
            Schedule.objects.create(
                staff=staff,
                start=now - timedelta(days=5),
                end=now - timedelta(days=5) + timedelta(hours=1),
                is_cancelled=(i < 5),
            )
        insights = generate_insights(store=store)
        cust_insights = [i for i in insights if i.category == 'customer']
        assert len(cust_insights) >= 1
        assert 'キャンセル' in cust_insights[0].title

    @pytest.mark.django_db
    def test_no_alert_low_cancellation(self, store):
        user = User.objects.create_user(username='good_staff', password='pass')
        staff = Staff.objects.create(name='GoodStaff', store=store, user=user)
        now = timezone.now()
        for i in range(10):
            Schedule.objects.create(
                staff=staff,
                start=now - timedelta(days=5),
                end=now - timedelta(days=5) + timedelta(hours=1),
                is_cancelled=(i == 0),
            )
        insights = generate_insights(store=store)
        cust_insights = [i for i in insights if i.category == 'customer']
        assert len(cust_insights) == 0


class TestBusinessInsightModel:
    """Test the BusinessInsight model itself."""

    @pytest.mark.django_db
    def test_create_insight(self, store):
        ins = BusinessInsight.objects.create(
            store=store, category='sales', severity='warning',
            title='Test', message='Test message',
        )
        assert ins.id is not None
        assert ins.is_read is False
        assert ins.created_at is not None

    @pytest.mark.django_db
    def test_str(self, store):
        ins = BusinessInsight.objects.create(
            store=store, category='sales', severity='info',
            title='テスト', message='メッセージ',
        )
        assert str(ins)

    @pytest.mark.django_db
    def test_data_json_field(self, store):
        ins = BusinessInsight.objects.create(
            store=store, category='inventory', severity='critical',
            title='Test', message='msg',
            data={'product_id': 1, 'stock': 0},
        )
        ins.refresh_from_db()
        assert ins.data['product_id'] == 1
        assert ins.data['stock'] == 0
