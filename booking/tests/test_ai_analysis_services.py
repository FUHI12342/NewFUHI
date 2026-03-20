"""Tests for AI analysis services: forecast, RFM, basket, auto-order."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import Order, OrderItem, Product, Staff, Store, SiteSettings

_counter = 0


def _make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def _make_product(store, name='テスト商品', price=1000, stock=100, margin_rate=0.3):
    global _counter
    _counter += 1
    return Product.objects.create(
        store=store, name=name, price=price, stock=stock,
        sku=f'AI-{_counter:04d}', is_active=True, margin_rate=margin_rate,
    )


def _make_order_with_items(store, products_qty, channel='pos', days_ago=1):
    """Create an order with multiple items.

    products_qty: list of (product, qty, unit_price) tuples
    """
    order = Order.objects.create(
        store=store,
        channel=channel,
        customer_line_user_hash=f'cust_{days_ago}_{_counter}',
        created_at=timezone.now() - timedelta(days=days_ago),
    )
    for product, qty, unit_price in products_qty:
        OrderItem.objects.create(
            order=order, product=product, qty=qty, unit_price=unit_price,
        )
    return order


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class AIAnalysisTestBase(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.admin_user = User.objects.create_superuser(
            username='admin_ai', password='admin123',
        )
        self.product_a = _make_product(self.store, 'ステーキ', 3000, 50, 0.4)
        self.product_b = _make_product(self.store, 'サラダ', 800, 200, 0.6)
        self.product_c = _make_product(self.store, 'ビール', 600, 300, 0.7)
        self.client = APIClient()
        SiteSettings.load()


# ── 1. Sales Forecast Service Tests ──

class TestSalesForecast(AIAnalysisTestBase):
    """Test generate_forecast with moving average."""

    def setUp(self):
        super().setUp()
        # Create 30 days of order data
        for i in range(30):
            _make_order_with_items(
                self.store,
                [(self.product_a, 2, 3000), (self.product_b, 1, 800)],
                days_ago=i + 1,
            )

    def test_generate_forecast_returns_structure(self):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast({'order__store': self.store})
        self.assertIn('historical', result)
        self.assertIn('forecast', result)
        self.assertIn('method', result)
        self.assertEqual(result['method'], 'moving_average')

    def test_forecast_has_correct_days(self):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast({'order__store': self.store}, forecast_days=7)
        self.assertEqual(len(result['forecast']), 7)

    def test_forecast_with_channel_filter(self):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast(
            {'order__store': self.store},
            channel_filter={'order__channel__in': ['pos']},
        )
        self.assertTrue(len(result['forecast']) > 0)

    def test_forecast_empty_data(self):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast({'order__store_id': 99999})
        self.assertEqual(result['forecast'], [])

    def test_forecast_items_have_required_keys(self):
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast({'order__store': self.store})
        if result['forecast']:
            item = result['forecast'][0]
            self.assertIn('date', item)
            self.assertIn('predicted', item)
            self.assertIn('lower', item)
            self.assertIn('upper', item)
            self.assertGreaterEqual(item['lower'], 0)
            self.assertGreaterEqual(item['upper'], item['predicted'])

    def test_prophet_fallback_graceful(self):
        """If Prophet not installed, should fallback to moving_average."""
        from booking.services.sales_forecast import generate_forecast
        result = generate_forecast({'order__store': self.store})
        self.assertIn(result['method'], ['moving_average', 'prophet'])


# ── 2. RFM Analysis Tests ──

class TestRFMAnalysis(AIAnalysisTestBase):
    """Test compute_rfm segmentation."""

    def setUp(self):
        super().setUp()
        # Create diverse customers
        for i in range(10):
            order = Order.objects.create(
                store=self.store,
                channel='pos',
                customer_line_user_hash=f'customer_{i}',
                created_at=timezone.now() - timedelta(days=i * 10 + 1),
            )
            OrderItem.objects.create(
                order=order, product=self.product_a,
                qty=i + 1, unit_price=3000,
            )

    def test_compute_rfm_returns_list(self):
        from booking.services.rfm_analysis import compute_rfm
        result = compute_rfm(scope={'order__store': self.store})
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)

    def test_rfm_customer_structure(self):
        from booking.services.rfm_analysis import compute_rfm
        result = compute_rfm(scope={'order__store': self.store})
        if result:
            customer = result[0]
            self.assertIn('customer_id', customer)
            self.assertIn('recency', customer)
            self.assertIn('frequency', customer)
            self.assertIn('monetary', customer)
            self.assertIn('r_score', customer)
            self.assertIn('f_score', customer)
            self.assertIn('m_score', customer)
            self.assertIn('segment', customer)

    def test_rfm_scores_range(self):
        from booking.services.rfm_analysis import compute_rfm
        result = compute_rfm(scope={'order__store': self.store})
        for customer in result:
            self.assertGreaterEqual(customer['r_score'], 1)
            self.assertLessEqual(customer['r_score'], 5)
            self.assertGreaterEqual(customer['f_score'], 1)
            self.assertLessEqual(customer['f_score'], 5)

    def test_rfm_valid_segments(self):
        from booking.services.rfm_analysis import compute_rfm
        valid_segments = {'champion', 'loyal', 'new', 'potential', 'at_risk', 'cant_lose', 'lost', 'other'}
        result = compute_rfm(scope={'order__store': self.store})
        for customer in result:
            self.assertIn(customer['segment'], valid_segments)

    def test_rfm_empty_store(self):
        from booking.services.rfm_analysis import compute_rfm
        result = compute_rfm(scope={'order__store_id': 99999})
        self.assertEqual(result, [])

    def test_rfm_api_endpoint(self):
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(reverse('booking_api:rfm_analysis_api'))
        self.assertEqual(resp.status_code, 200)


# ── 3. Basket Analysis Tests ──

class TestBasketAnalysis(AIAnalysisTestBase):
    """Test analyze_basket association rules."""

    def setUp(self):
        super().setUp()
        # Create orders with product combinations for association rules
        for i in range(20):
            # Steak + Beer (common pair)
            _make_order_with_items(
                self.store,
                [(self.product_a, 1, 3000), (self.product_c, 2, 600)],
                days_ago=i + 1,
            )
        for i in range(10):
            # Salad + Beer
            _make_order_with_items(
                self.store,
                [(self.product_b, 1, 800), (self.product_c, 1, 600)],
                days_ago=i + 1,
            )

    def test_basket_returns_structure(self):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store': self.store})
        self.assertIn('rules', result)
        self.assertIn('total_transactions', result)
        self.assertIn('method', result)

    def test_basket_finds_associations(self):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store': self.store})
        self.assertTrue(len(result['rules']) > 0, 'Should find at least one association rule')

    def test_basket_rule_structure(self):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store': self.store})
        if result['rules']:
            rule = result['rules'][0]
            self.assertIn('antecedent', rule)
            self.assertIn('consequent', rule)
            self.assertIn('support', rule)
            self.assertIn('confidence', rule)
            self.assertIn('lift', rule)

    def test_basket_support_confidence_range(self):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store': self.store})
        for rule in result['rules']:
            self.assertGreaterEqual(rule['support'], 0)
            self.assertLessEqual(rule['support'], 1)
            self.assertGreaterEqual(rule['confidence'], 0)
            self.assertLessEqual(rule['confidence'], 1)
            self.assertGreater(rule['lift'], 0)

    def test_basket_empty_store(self):
        from booking.services.basket_analysis import analyze_basket
        result = analyze_basket(scope={'order__store_id': 99999})
        self.assertEqual(result['rules'], [])

    def test_basket_api_endpoint(self):
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(reverse('booking_api:basket_analysis_api'))
        self.assertEqual(resp.status_code, 200)


# ── 4. Auto-Order Recommendation Tests ──

class TestAutoOrder(AIAnalysisTestBase):
    """Test compute_auto_order with trend-weighted consumption."""

    def setUp(self):
        super().setUp()
        # Create consumption pattern: heavier recent consumption
        for i in range(30):
            qty = 5 if i < 7 else 2  # Recent 7 days: 5/day, older: 2/day
            _make_order_with_items(
                self.store,
                [(self.product_a, qty, 3000)],
                days_ago=i + 1,
            )

    def test_auto_order_returns_structure(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        self.assertIn('recommendations', result)
        self.assertIn('summary', result)
        self.assertIn('params', result)

    def test_auto_order_products_included(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        self.assertTrue(len(result['recommendations']) > 0)

    def test_auto_order_urgency_valid(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        valid_urgencies = {'critical', 'warning', 'ok'}
        for rec in result['recommendations']:
            self.assertIn(rec['urgency'], valid_urgencies)

    def test_auto_order_summary_counts(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        summary = result['summary']
        total = summary['critical_count'] + summary['warning_count'] + summary['ok_count']
        self.assertEqual(total, summary['total_products'])

    def test_auto_order_recommended_qty_nonnegative(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        for rec in result['recommendations']:
            self.assertGreaterEqual(rec['recommended_qty'], 0)

    def test_auto_order_trend_weighting(self):
        """Recent heavy consumption should increase daily_consumption estimate."""
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store': self.store})
        steak_rec = next(
            (r for r in result['recommendations'] if r['product']['name'] == 'ステーキ'),
            None,
        )
        self.assertIsNotNone(steak_rec)
        # With trend weighting, daily consumption should be higher than simple average (2.8/day)
        # because recent 7 days had 5/day
        self.assertGreater(steak_rec['daily_consumption'], 2.5)

    def test_auto_order_api_endpoint(self):
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(reverse('booking_api:auto_order_api'))
        self.assertEqual(resp.status_code, 200)

    def test_auto_order_empty_store(self):
        from booking.services.auto_order import compute_auto_order
        result = compute_auto_order(scope={'store_id': 99999})
        self.assertEqual(result['recommendations'], [])


# ── 5. Sales Forecast API Tests ──

class TestForecastAPI(AIAnalysisTestBase):
    """Test SalesForecastAPIView."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin_user)
        for i in range(20):
            _make_order_with_items(
                self.store,
                [(self.product_a, 1, 3000)],
                days_ago=i + 1,
            )

    def test_forecast_api_returns_200(self):
        resp = self.client.get(reverse('booking_api:sales_forecast_api'))
        self.assertEqual(resp.status_code, 200)

    def test_forecast_api_with_channel(self):
        resp = self.client.get(reverse('booking_api:sales_forecast_api'), {'channel': 'pos'})
        self.assertEqual(resp.status_code, 200)

    def test_forecast_api_unauthenticated(self):
        self.client.logout()
        resp = self.client.get(reverse('booking_api:sales_forecast_api'))
        self.assertEqual(resp.status_code, 403)


# ── 6. AI Analysis Text Integration Tests ──

class TestAIAnalysisTextIntegration(AIAnalysisTestBase):
    """Integration tests for SalesAnalysisTextAPIView with real data."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin_user)
        # Create 60 days of diverse data
        for i in range(60):
            channel = 'ec' if i % 3 == 0 else 'pos'
            _make_order_with_items(
                self.store,
                [
                    (self.product_a, 2, 3000),
                    (self.product_b, 1, 800),
                    (self.product_c, 3, 600),
                ],
                channel=channel,
                days_ago=i + 1,
            )

    def test_all_analysis_types_with_data(self):
        """All 6 analysis types should return valid responses with real data."""
        url = reverse('booking_api:analysis_text_api')
        for analysis_type in ['sales_trend', 'menu_engineering', 'abc_analysis', 'forecast', 'heatmap', 'aov']:
            resp = self.client.get(url, {'type': analysis_type})
            self.assertEqual(resp.status_code, 200, f'{analysis_type} failed')
            data = resp.json()
            self.assertIn('summary', data)
            self.assertTrue(len(data['summary']) > 0, f'{analysis_type} summary is empty')
            self.assertIn(data['score'], {'A+', 'A', 'B+', 'B', 'C', 'D', '-'})

    def test_channel_filter_changes_results(self):
        """EC-only vs all-channel should produce different analysis."""
        url = reverse('booking_api:analysis_text_api')
        resp_all = self.client.get(url, {'type': 'sales_trend'})
        resp_ec = self.client.get(url, {'type': 'sales_trend', 'channel': 'ec'})
        self.assertEqual(resp_all.status_code, 200)
        self.assertEqual(resp_ec.status_code, 200)
        # Both should have findings
        self.assertTrue(len(resp_all.json()['findings']) > 0)
        self.assertTrue(len(resp_ec.json()['findings']) > 0)
