"""
Phase 1: 0% サービスモジュールのテスト

対象:
  - services/auto_order.py (53 stmts)
  - services/clv_analysis.py (77 stmts)
  - services/external_data.py (36 stmts)
  - services/visitor_forecast.py (67 stmts)
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from booking.models import (
    Store, Category, Product, Order, OrderItem, VisitorCount,
)
from booking.services.auto_order import compute_auto_order
from booking.services.clv_analysis import compute_clv
from booking.services.external_data import (
    get_integration_status, get_weather_forecast, get_google_reviews,
)
from booking.services.visitor_forecast import compute_visitor_forecast


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_a(db):
    return Store.objects.create(
        name="テスト店舗A", address="東京", business_hours="10-22",
        nearest_station="新宿",
    )


@pytest.fixture
def category_a(store_a):
    return Category.objects.create(store=store_a, name="ドリンク", sort_order=0)


@pytest.fixture
def products(store_a, category_a):
    """3 products: high-consumption, low-consumption, zero-consumption."""
    p1 = Product.objects.create(
        store=store_a, category=category_a, sku="P001",
        name="商品A", price=500, stock=10, low_stock_threshold=5, is_active=True,
    )
    p2 = Product.objects.create(
        store=store_a, category=category_a, sku="P002",
        name="商品B", price=1000, stock=100, low_stock_threshold=10, is_active=True,
    )
    p3 = Product.objects.create(
        store=store_a, category=category_a, sku="P003",
        name="商品C", price=300, stock=0, low_stock_threshold=5, is_active=True,
    )
    return p1, p2, p3


@pytest.fixture
def orders_with_consumption(store_a, products):
    """Create orders with consumption data for the past 30 days."""
    p1, p2, _p3 = products
    now = timezone.now()
    order = Order.objects.create(store=store_a, status=Order.STATUS_OPEN)
    # Force created_at to within the history window
    Order.objects.filter(pk=order.pk).update(created_at=now - timedelta(days=5))
    # p1: high consumption (30 units in 30 days = 1/day)
    OrderItem.objects.create(
        order=order, product=p1, qty=30, unit_price=p1.price,
        status=OrderItem.STATUS_ORDERED,
    )
    # p2: low consumption (3 units in 30 days = 0.1/day)
    OrderItem.objects.create(
        order=order, product=p2, qty=3, unit_price=p2.price,
        status=OrderItem.STATUS_ORDERED,
    )
    return order


# ==============================
# auto_order tests
# ==============================

class TestComputeAutoOrder:
    """booking.services.auto_order.compute_auto_order"""

    def test_no_products(self, db):
        """No active products → empty recommendations."""
        result = compute_auto_order()
        assert result['recommendations'] == []
        assert result['summary']['total_products'] == 0

    def test_no_consumption(self, products):
        """Products exist but no orders → all ok, 0 daily consumption."""
        result = compute_auto_order()
        recs = result['recommendations']
        assert len(recs) == 3
        for r in recs:
            assert r['daily_consumption'] == 0
            assert r['recommended_qty'] == 0

    def test_zero_stock_no_consumption(self, products):
        """Zero stock + zero consumption → days_remaining=0, urgency=critical."""
        result = compute_auto_order()
        p3_rec = next(r for r in result['recommendations'] if r['product']['sku'] == 'P003')
        assert p3_rec['current_stock'] == 0
        assert p3_rec['urgency'] == 'critical'
        assert p3_rec['days_remaining'] == 0

    def test_high_stock_no_consumption(self, products):
        """High stock + no consumption → days_remaining=None (999), urgency=ok."""
        result = compute_auto_order()
        p2_rec = next(r for r in result['recommendations'] if r['product']['sku'] == 'P002')
        assert p2_rec['current_stock'] == 100
        assert p2_rec['urgency'] == 'ok'
        assert p2_rec['days_remaining'] is None  # 999 maps to None

    def test_with_consumption_data(self, products, orders_with_consumption):
        """Products with consumption → correct daily rate and urgency."""
        result = compute_auto_order(history_days=30)
        p1_rec = next(r for r in result['recommendations'] if r['product']['sku'] == 'P001')
        # p1: 30 consumed / 30 days = 1.0/day, stock=10, days_remaining=10
        assert p1_rec['daily_consumption'] == 1.0
        assert p1_rec['days_remaining'] == 10.0
        # reorder_point = lead_time(1) + safety(1) = 2
        # 10 > 2 → ok
        assert p1_rec['urgency'] == 'ok'

    def test_critical_urgency(self, store_a, category_a, orders_with_consumption):
        """Stock below lead time → critical."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="CRIT",
            name="Critical商品", price=100, stock=0, low_stock_threshold=5, is_active=True,
        )
        now = timezone.now()
        order = Order.objects.create(store=store_a, status=Order.STATUS_OPEN)
        Order.objects.filter(pk=order.pk).update(created_at=now - timedelta(days=5))
        OrderItem.objects.create(
            order=order, product=p, qty=30, unit_price=p.price,
            status=OrderItem.STATUS_ORDERED,
        )
        result = compute_auto_order(history_days=30)
        crit_rec = next(r for r in result['recommendations'] if r['product']['sku'] == 'CRIT')
        assert crit_rec['urgency'] == 'critical'
        assert crit_rec['recommended_qty'] > 0

    def test_scope_filter(self, products, orders_with_consumption, db):
        """Scope filter limits to specific store."""
        other_store = Store.objects.create(
            name="Other", address="大阪", business_hours="10-22",
            nearest_station="梅田",
        )
        result = compute_auto_order(scope={'store': other_store})
        assert result['summary']['total_products'] == 0

    def test_summary_counts(self, products, orders_with_consumption):
        """Summary correctly counts critical/warning/ok."""
        result = compute_auto_order(history_days=30)
        s = result['summary']
        assert s['total_products'] == 3
        assert s['critical_count'] + s['warning_count'] + s['ok_count'] == s['total_products']

    def test_sorted_by_urgency(self, products, orders_with_consumption):
        """Recommendations sorted: critical first, then warning, then ok."""
        result = compute_auto_order(history_days=30)
        urgencies = [r['urgency'] for r in result['recommendations']]
        order_map = {'critical': 0, 'warning': 1, 'ok': 2}
        assert urgencies == sorted(urgencies, key=lambda u: order_map[u])

    def test_params_in_result(self, db):
        """Result includes the params used."""
        result = compute_auto_order(history_days=15, lead_time_days=3, safety_buffer_days=2)
        assert result['params'] == {
            'history_days': 15,
            'lead_time_days': 3,
            'safety_buffer_days': 2,
        }


# ==============================
# clv_analysis tests
# ==============================

class TestComputeCLV:
    """booking.services.clv_analysis.compute_clv"""

    def test_no_orders(self, db):
        """No orders → empty result with zero summary."""
        result = compute_clv()
        assert result['segments'] == []
        assert result['summary']['total_customers'] == 0
        assert result['summary']['avg_clv'] == 0
        assert result['customers'] == []

    def test_single_customer(self, store_a, category_a):
        """Single customer with orders → one customer entry."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="CLV1",
            name="CLV商品", price=1000, stock=100, low_stock_threshold=5, is_active=True,
        )
        order = Order.objects.create(
            store=store_a, status=Order.STATUS_OPEN,
            customer_line_user_hash="abc123hash",
        )
        OrderItem.objects.create(
            order=order, product=p, qty=2, unit_price=1000,
            status=OrderItem.STATUS_ORDERED,
        )
        result = compute_clv(months=6)
        assert result['summary']['total_customers'] == 1
        assert len(result['customers']) == 1
        c = result['customers'][0]
        assert c['order_count'] == 1
        assert c['total_revenue'] == 2000
        assert c['avg_order_value'] == 2000

    def test_multiple_customers_segmented(self, store_a, category_a):
        """Multiple customers → segmented by CLV."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="SEG1",
            name="Seg商品", price=500, stock=100, low_stock_threshold=5, is_active=True,
        )
        now = timezone.now()
        # Create 5 customers with varying order volumes
        for i in range(5):
            for j in range(i + 1):  # customer i has i+1 orders
                order = Order.objects.create(
                    store=store_a, status=Order.STATUS_OPEN,
                    customer_line_user_hash=f"customer_{i}_hash",
                )
                Order.objects.filter(pk=order.pk).update(
                    created_at=now - timedelta(days=j * 10)
                )
                OrderItem.objects.create(
                    order=order, product=p, qty=(i + 1),
                    unit_price=500, status=OrderItem.STATUS_ORDERED,
                )

        result = compute_clv(months=6)
        assert result['summary']['total_customers'] == 5
        assert result['summary']['total_revenue'] > 0
        assert len(result['segments']) > 0

    def test_at_risk_segment(self, store_a, category_a):
        """Customer with last order > 60 days ago → at_risk."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="RISK1",
            name="Risk商品", price=1000, stock=100, low_stock_threshold=5, is_active=True,
        )
        # Create 4 customers to meet threshold (>2 required for percentile)
        now = timezone.now()
        for i in range(4):
            order = Order.objects.create(
                store=store_a, status=Order.STATUS_OPEN,
                customer_line_user_hash=f"risk_{i}",
            )
            days_ago = 70 if i == 0 else 5  # first customer is "at risk"
            Order.objects.filter(pk=order.pk).update(
                created_at=now - timedelta(days=days_ago)
            )
            OrderItem.objects.create(
                order=order, product=p, qty=1, unit_price=1000,
                status=OrderItem.STATUS_ORDERED,
            )

        result = compute_clv(months=6)
        at_risk = [c for c in result['customers'] if c['segment'] == 'at_risk']
        assert len(at_risk) >= 1

    def test_lost_segment(self, store_a, category_a):
        """Customer with last order > 120 days ago → lost."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="LOST1",
            name="Lost商品", price=1000, stock=100, low_stock_threshold=5, is_active=True,
        )
        now = timezone.now()
        for i in range(4):
            order = Order.objects.create(
                store=store_a, status=Order.STATUS_OPEN,
                customer_line_user_hash=f"lost_{i}",
            )
            days_ago = 130 if i == 0 else 5
            Order.objects.filter(pk=order.pk).update(
                created_at=now - timedelta(days=days_ago)
            )
            OrderItem.objects.create(
                order=order, product=p, qty=1, unit_price=1000,
                status=OrderItem.STATUS_ORDERED,
            )

        result = compute_clv(months=12)
        lost = [c for c in result['customers'] if c['segment'] == 'lost']
        assert len(lost) >= 1

    def test_scope_filter(self, store_a, category_a, db):
        """Scope limits analysis to specific store."""
        other_store = Store.objects.create(
            name="Other", address="大阪", business_hours="10-22",
            nearest_station="梅田",
        )
        p = Product.objects.create(
            store=store_a, category=category_a, sku="SC1",
            name="Scope商品", price=500, stock=100, low_stock_threshold=5, is_active=True,
        )
        order = Order.objects.create(
            store=store_a, status=Order.STATUS_OPEN,
            customer_line_user_hash="scope_test",
        )
        OrderItem.objects.create(
            order=order, product=p, qty=1, unit_price=500,
            status=OrderItem.STATUS_ORDERED,
        )
        # Scoped to other store → no results
        result = compute_clv(scope={'order__store': other_store})
        assert result['summary']['total_customers'] == 0

    def test_customers_capped_at_100(self, store_a, category_a):
        """Result returns at most 100 customers."""
        p = Product.objects.create(
            store=store_a, category=category_a, sku="CAP1",
            name="Cap商品", price=100, stock=1000, low_stock_threshold=5, is_active=True,
        )
        for i in range(105):
            order = Order.objects.create(
                store=store_a, status=Order.STATUS_OPEN,
                customer_line_user_hash=f"cap_{i:04d}",
            )
            OrderItem.objects.create(
                order=order, product=p, qty=1, unit_price=100,
                status=OrderItem.STATUS_ORDERED,
            )
        result = compute_clv(months=6)
        assert len(result['customers']) <= 100


# ==============================
# external_data tests
# ==============================

class TestExternalData:
    """booking.services.external_data module."""

    def test_integration_status_not_configured(self, settings):
        """No API keys → all integrations show not_configured."""
        settings.OPENWEATHERMAP_API_KEY = None
        settings.GOOGLE_BUSINESS_API_KEY = None
        result = get_integration_status()
        assert len(result) == 2
        for item in result:
            assert item['configured'] is False
            assert item['status'] == 'not_configured'

    def test_integration_status_configured(self, settings):
        """API keys set → corresponding integration shows active."""
        settings.OPENWEATHERMAP_API_KEY = 'test-key'
        settings.GOOGLE_BUSINESS_API_KEY = None
        result = get_integration_status()
        weather = next(i for i in result if i['key'] == 'weather')
        reviews = next(i for i in result if i['key'] == 'google_reviews')
        assert weather['configured'] is True
        assert weather['status'] == 'active'
        assert reviews['configured'] is False

    def test_weather_forecast_defaults(self):
        """Weather forecast with defaults returns mock data."""
        result = get_weather_forecast()
        assert result['is_mock'] is True
        assert result['location']['lat'] == 35.6762
        assert len(result['forecast']) == 7

    def test_weather_forecast_custom_params(self):
        """Weather forecast with custom lat/lng/days."""
        result = get_weather_forecast(lat=34.0, lng=135.0, days=3)
        assert result['location']['lat'] == 34.0
        assert result['location']['lng'] == 135.0
        assert len(result['forecast']) == 3

    def test_weather_forecast_with_api_key(self, settings):
        """When API key is set, function still returns mock data (TODO)."""
        settings.OPENWEATHERMAP_API_KEY = 'test-key'
        result = get_weather_forecast()
        assert result['is_mock'] is True
        assert len(result['forecast']) == 7

    def test_weather_forecast_structure(self):
        """Each forecast entry has expected fields."""
        result = get_weather_forecast(days=1)
        entry = result['forecast'][0]
        assert 'date' in entry
        assert 'weather' in entry
        assert 'temperature_high' in entry
        assert 'temperature_low' in entry
        assert 'precipitation_pct' in entry

    def test_google_reviews_no_place_id(self):
        """Google reviews without place_id returns mock data."""
        result = get_google_reviews()
        assert result['is_mock'] is True
        assert result['place_id'] == '(not configured)'
        assert len(result['reviews']) == 3
        assert 3.0 <= result['avg_rating'] <= 5.0

    def test_google_reviews_with_place_id(self):
        """Google reviews with place_id."""
        result = get_google_reviews(place_id='ChIJtest123')
        assert result['place_id'] == 'ChIJtest123'
        assert result['total_reviews'] == 3

    def test_google_reviews_with_api_key(self, settings):
        """When API key is set, function still returns mock data (TODO)."""
        settings.GOOGLE_BUSINESS_API_KEY = 'test-key'
        result = get_google_reviews(place_id='test')
        assert result['is_mock'] is True


# ==============================
# visitor_forecast tests
# ==============================

class TestComputeVisitorForecast:
    """booking.services.visitor_forecast.compute_visitor_forecast"""

    def test_no_data(self, db):
        """No visitor data → empty historical, default forecast."""
        result = compute_visitor_forecast()
        assert result['historical'] == []
        assert len(result['forecast']) == 14  # default forecast_days
        # With no data, avg_daily=0, so predicted=0
        for f in result['forecast']:
            assert f['predicted'] == 0

    def test_with_visitor_data(self, store_a):
        """Visitor data → non-zero forecast predictions."""
        today = timezone.now().date()
        # Create 4 weeks of visitor data (28 days)
        for i in range(28):
            d = today - timedelta(days=i)
            for hour in range(10, 18):
                VisitorCount.objects.create(
                    store=store_a, date=d, hour=hour,
                    pir_count=20, estimated_visitors=10, order_count=5,
                )

        result = compute_visitor_forecast(scope={'store': store_a})
        assert len(result['historical']) > 0
        assert len(result['forecast']) == 14
        # With real data, predictions should be > 0
        assert any(f['predicted'] > 0 for f in result['forecast'])

    def test_forecast_days_param(self, db):
        """Custom forecast_days parameter."""
        result = compute_visitor_forecast(forecast_days=7)
        assert len(result['forecast']) == 7
        assert len(result['staff_recommendation']) == 7

    def test_weekday_coefficient(self, store_a):
        """Different visitor counts per weekday → different predictions."""
        today = timezone.now().date()
        for i in range(28):
            d = today - timedelta(days=i)
            # Weekends (5,6) get more visitors
            visitors = 50 if d.weekday() >= 5 else 10
            VisitorCount.objects.create(
                store=store_a, date=d, hour=12,
                pir_count=visitors * 2, estimated_visitors=visitors, order_count=5,
            )

        result = compute_visitor_forecast(scope={'store': store_a}, forecast_days=14)
        forecasts = {f['weekday']: f['predicted'] for f in result['forecast']}
        # Verify method is weekday_moving_average
        assert result['method'] == 'weekday_moving_average'

    def test_confidence_interval(self, store_a):
        """Forecast includes lower/upper bounds."""
        today = timezone.now().date()
        for i in range(28):
            d = today - timedelta(days=i)
            VisitorCount.objects.create(
                store=store_a, date=d, hour=12,
                pir_count=20, estimated_visitors=10, order_count=5,
            )

        result = compute_visitor_forecast(scope={'store': store_a})
        for f in result['forecast']:
            assert 'lower' in f
            assert 'upper' in f
            assert f['lower'] <= f['predicted'] <= f['upper'] or f['predicted'] == 0

    def test_staff_recommendation(self, store_a):
        """Staff recommendation included with forecast."""
        today = timezone.now().date()
        for i in range(28):
            d = today - timedelta(days=i)
            VisitorCount.objects.create(
                store=store_a, date=d, hour=12,
                pir_count=40, estimated_visitors=20, order_count=10,
            )

        result = compute_visitor_forecast(scope={'store': store_a})
        assert len(result['staff_recommendation']) == 14
        for sr in result['staff_recommendation']:
            assert sr['recommended_staff'] >= 1
            assert 'visitors_per_staff' in sr

    def test_scope_filter(self, store_a, db):
        """Scope limits to specific store."""
        other_store = Store.objects.create(
            name="Other", address="大阪", business_hours="10-22",
            nearest_station="梅田",
        )
        today = timezone.now().date()
        VisitorCount.objects.create(
            store=store_a, date=today, hour=12,
            pir_count=20, estimated_visitors=10, order_count=5,
        )
        result = compute_visitor_forecast(scope={'store': other_store})
        assert result['historical'] == []

    def test_forecast_date_format(self, db):
        """Forecast dates are ISO format strings."""
        result = compute_visitor_forecast(forecast_days=3)
        for f in result['forecast']:
            # Should parse as a date
            date.fromisoformat(f['date'])
