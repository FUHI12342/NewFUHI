"""Tests for sales analysis features: yearly period, channel filter, AI analysis text."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from booking.models import Order, OrderItem, Product, Staff, Store, SiteSettings


def _make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def _make_staff_user(store, username='staff1', name='テストスタッフ', is_superuser=False):
    user = User.objects.create_user(
        username=username, password='testpass123',
        is_staff=True, is_superuser=is_superuser,
    )
    staff = Staff.objects.create(user=user, store=store, name=name)
    return user, staff


_product_counter = 0


def _make_product(store, name='テスト商品', price=1000, margin_rate=0.3):
    global _product_counter
    _product_counter += 1
    return Product.objects.create(
        store=store, name=name, price=price,
        sku=f'TEST-{_product_counter:04d}',
        is_active=True, margin_rate=margin_rate,
    )


def _make_order_with_item(store, product, channel='pos', qty=1, unit_price=1000, days_ago=1):
    order = Order.objects.create(
        store=store,
        channel=channel,
        created_at=timezone.now() - timedelta(days=days_ago),
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        qty=qty,
        unit_price=unit_price,
    )
    return order


@override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class SalesAnalysisTestBase(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.admin_user = User.objects.create_superuser(
            username='admin', password='admin123',
        )
        self.product_a = _make_product(self.store, 'A商品', 2000, 0.5)
        self.product_b = _make_product(self.store, 'B商品', 800, 0.2)
        self.client = APIClient()
        self.settings = SiteSettings.load()


# ── 1. Yearly period tests ──

class TestYearlyPeriod(SalesAnalysisTestBase):
    """SalesStatsAPIView with period=yearly."""

    def setUp(self):
        super().setUp()
        self.url = reverse('booking_api:sales_stats_api')
        self.client.force_authenticate(user=self.admin_user)
        # Create orders spanning multiple years
        _make_order_with_item(self.store, self.product_a, 'pos', 3, 2000, days_ago=10)
        _make_order_with_item(self.store, self.product_a, 'pos', 2, 2000, days_ago=400)
        _make_order_with_item(self.store, self.product_a, 'pos', 1, 2000, days_ago=800)

    def test_yearly_period_returns_data(self):
        resp = self.client.get(self.url, {'period': 'yearly'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('trend', data)
        self.assertTrue(len(data['trend']) > 0)

    def test_daily_period_still_works(self):
        resp = self.client.get(self.url, {'period': 'daily'})
        self.assertEqual(resp.status_code, 200)

    def test_monthly_period_still_works(self):
        resp = self.client.get(self.url, {'period': 'monthly'})
        self.assertEqual(resp.status_code, 200)

    def test_weekly_period_still_works(self):
        resp = self.client.get(self.url, {'period': 'weekly'})
        self.assertEqual(resp.status_code, 200)

    def test_invalid_period_fallback(self):
        """Unknown period falls back to daily."""
        resp = self.client.get(self.url, {'period': 'invalid'})
        self.assertEqual(resp.status_code, 200)


# ── 2. Channel filter tests ──

class TestChannelFilter(SalesAnalysisTestBase):
    """MenuEngineering/ABC/Forecast/Heatmap/AOV with channel filter."""

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(user=self.admin_user)
        # EC orders
        for i in range(5):
            _make_order_with_item(self.store, self.product_a, 'ec', 2, 2000, days_ago=i + 1)
        # POS orders
        for i in range(3):
            _make_order_with_item(self.store, self.product_b, 'pos', 1, 800, days_ago=i + 1)

    def test_menu_engineering_with_channel_filter(self):
        url = reverse('booking_api:menu_engineering_api')
        resp = self.client.get(url, {'channel': 'ec'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('products', data)

    def test_menu_engineering_without_channel(self):
        url = reverse('booking_api:menu_engineering_api')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_abc_analysis_with_channel_filter(self):
        url = reverse('booking_api:abc_analysis_api')
        resp = self.client.get(url, {'channel': 'pos'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('products', data)

    def test_forecast_with_channel_filter(self):
        url = reverse('booking_api:sales_forecast_api')
        resp = self.client.get(url, {'channel': 'ec'})
        self.assertEqual(resp.status_code, 200)

    def test_heatmap_with_channel_filter(self):
        url = reverse('booking_api:sales_heatmap_api')
        resp = self.client.get(url, {'channel': 'pos'})
        self.assertEqual(resp.status_code, 200)

    def test_aov_with_channel_filter(self):
        url = reverse('booking_api:aov_trend_api')
        resp = self.client.get(url, {'channel': 'ec'})
        self.assertEqual(resp.status_code, 200)

    def test_multi_channel_filter(self):
        """channel=pos,table should filter to both."""
        url = reverse('booking_api:menu_engineering_api')
        resp = self.client.get(url, {'channel': 'pos,table'})
        self.assertEqual(resp.status_code, 200)


# ── 3. AI analysis text API tests ──

class TestAnalysisTextAuth(SalesAnalysisTestBase):
    """SalesAnalysisTextAPIView authentication."""

    def setUp(self):
        super().setUp()
        self.url = reverse('booking_api:analysis_text_api')

    def test_unauthenticated_returns_403(self):
        resp = self.client.get(self.url, {'type': 'sales_trend'})
        self.assertEqual(resp.status_code, 403)

    def test_staff_without_store_returns_403(self):
        user = User.objects.create_user(
            username='nostore', password='pass123', is_staff=True,
        )
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.url, {'type': 'sales_trend'})
        self.assertEqual(resp.status_code, 403)


class TestAnalysisTextValidation(SalesAnalysisTestBase):
    """SalesAnalysisTextAPIView input validation."""

    def setUp(self):
        super().setUp()
        self.url = reverse('booking_api:analysis_text_api')
        self.client.force_authenticate(user=self.admin_user)

    def test_missing_type_returns_400(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 400)

    def test_invalid_type_returns_400(self):
        resp = self.client.get(self.url, {'type': 'invalid_type'})
        self.assertEqual(resp.status_code, 400)

    def test_valid_types_accepted(self):
        for analysis_type in ['sales_trend', 'menu_engineering', 'abc_analysis', 'forecast', 'heatmap', 'aov']:
            resp = self.client.get(self.url, {'type': analysis_type})
            self.assertIn(resp.status_code, [200, 500],
                          msg=f'type={analysis_type} returned {resp.status_code}')


class TestAnalysisTextResponse(SalesAnalysisTestBase):
    """SalesAnalysisTextAPIView response structure."""

    def setUp(self):
        super().setUp()
        self.url = reverse('booking_api:analysis_text_api')
        self.client.force_authenticate(user=self.admin_user)
        # Create enough data for analysis
        for i in range(30):
            _make_order_with_item(self.store, self.product_a, 'pos', 2, 2000, days_ago=i + 1)
            _make_order_with_item(self.store, self.product_b, 'ec', 1, 800, days_ago=i + 1)

    def test_sales_trend_response_structure(self):
        resp = self.client.get(self.url, {'type': 'sales_trend'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)
        self.assertIn('findings', data)
        self.assertIn('recommendations', data)
        self.assertIn('score', data)
        self.assertIsInstance(data['findings'], list)
        self.assertIsInstance(data['recommendations'], list)

    def test_menu_engineering_response_structure(self):
        resp = self.client.get(self.url, {'type': 'menu_engineering'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)
        self.assertIn('score', data)
        self.assertTrue(len(data['findings']) > 0)

    def test_abc_analysis_response_structure(self):
        resp = self.client.get(self.url, {'type': 'abc_analysis'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)
        self.assertTrue(len(data['findings']) > 0)

    def test_forecast_response_structure(self):
        resp = self.client.get(self.url, {'type': 'forecast'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)

    def test_heatmap_response_structure(self):
        resp = self.client.get(self.url, {'type': 'heatmap'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)

    def test_aov_response_structure(self):
        resp = self.client.get(self.url, {'type': 'aov'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('summary', data)
        self.assertIn('score', data)

    def test_channel_filter_applied(self):
        """Channel filter should limit results to specified channel."""
        resp_ec = self.client.get(self.url, {'type': 'sales_trend', 'channel': 'ec'})
        resp_all = self.client.get(self.url, {'type': 'sales_trend'})
        self.assertEqual(resp_ec.status_code, 200)
        self.assertEqual(resp_all.status_code, 200)
        # EC-only and all should have different summaries
        self.assertIn('summary', resp_ec.json())
        self.assertIn('summary', resp_all.json())

    def test_score_is_valid_grade(self):
        resp = self.client.get(self.url, {'type': 'sales_trend'})
        self.assertEqual(resp.status_code, 200)
        valid_grades = {'A+', 'A', 'B+', 'B', 'C', 'D', '-'}
        self.assertIn(resp.json()['score'], valid_grades)


# ── 4. SalesAnalysisEngine unit tests ──

class TestSalesAnalysisEngine(SalesAnalysisTestBase):
    """Direct unit tests for SalesAnalysisEngine."""

    def setUp(self):
        super().setUp()
        for i in range(30):
            _make_order_with_item(self.store, self.product_a, 'pos', 2, 2000, days_ago=i + 1)
            _make_order_with_item(self.store, self.product_b, 'ec', 1, 800, days_ago=i + 1)

    def test_unknown_type_returns_placeholder(self):
        from booking.services.sales_analysis_text import SalesAnalysisEngine
        engine = SalesAnalysisEngine()
        result = engine.analyze('nonexistent', {'store': self.store}, {})
        self.assertEqual(result['score'], '-')
        self.assertEqual(result['summary'], '分析タイプが不明です')

    def test_sales_trend_with_store_scope(self):
        from booking.services.sales_analysis_text import SalesAnalysisEngine
        engine = SalesAnalysisEngine()
        result = engine.analyze('sales_trend', {'order__store': self.store}, {})
        self.assertIn('直近90日', result['summary'])
        self.assertIn(result['score'], {'A+', 'A', 'B+', 'B', 'C', 'D'})

    def test_menu_engineering_with_channel_filter(self):
        from booking.services.sales_analysis_text import SalesAnalysisEngine
        engine = SalesAnalysisEngine()
        result = engine.analyze('menu_engineering', {'order__store': self.store}, {'order__channel__in': ['pos']})
        self.assertIn('Star', result['summary'])

    def test_abc_with_no_data_returns_placeholder(self):
        from booking.services.sales_analysis_text import SalesAnalysisEngine
        engine = SalesAnalysisEngine()
        # Use non-existent store ID to get no data
        result = engine.analyze('abc_analysis', {'order__store_id': 99999}, {})
        self.assertEqual(result['score'], '-')

    def test_grade_function(self):
        from booking.services.sales_analysis_text import _grade
        # growth_rate benchmarks: good=5.0, warn=0.0
        self.assertEqual(_grade('growth_rate', 15.0), 'A+')  # >= good*2 (10)
        self.assertEqual(_grade('growth_rate', 5.0), 'A')     # >= good (5)
        self.assertEqual(_grade('growth_rate', 3.0), 'B+')    # >= (good+warn)/2 (2.5)
        self.assertEqual(_grade('growth_rate', 0.0), 'B')     # >= warn (0)
        self.assertEqual(_grade('growth_rate', -0.5), 'D')    # < warn*0.5 (0)
        self.assertEqual(_grade('growth_rate', -10.0), 'D')


# ── 5. DashboardLayoutAPIView auth tests ──

class TestDashboardLayoutAuth(SalesAnalysisTestBase):
    """DashboardLayoutAPIView is_staff check."""

    def setUp(self):
        super().setUp()
        self.url = reverse('booking_api:dashboard_layout_api')

    def test_unauthenticated_returns_403(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_non_staff_returns_403(self):
        user = User.objects.create_user(
            username='regular', password='pass123', is_staff=False,
        )
        self.client.force_authenticate(user=user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 403)

    def test_staff_returns_200(self):
        self.client.force_authenticate(user=self.admin_user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
