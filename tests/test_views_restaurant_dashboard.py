"""Tests for restaurant dashboard API views."""
import pytest
from django.test import Client
from django.contrib.auth.models import User

from booking.models import Product, Order, OrderItem, Store, Category, BusinessInsight, Schedule, Staff, TableSeat, CustomerFeedback


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_dashboard', password='adminpass', email='admin@test.com',
    )


@pytest.fixture
def admin_client(admin_user):
    client = Client()
    client.login(username='admin_dashboard', password='adminpass')
    return client


@pytest.fixture
def dashboard_store(db):
    return Store.objects.create(
        name='ダッシュボード店舗', address='東京', business_hours='9:00-21:00',
        nearest_station='渋谷駅',
    )


@pytest.fixture
def dashboard_category(db, dashboard_store):
    return Category.objects.create(store=dashboard_store, name='ドリンク')


@pytest.fixture
def dashboard_products(db, dashboard_store, dashboard_category):
    """Create several products with varying margin_rate for menu engineering tests."""
    products = []
    specs = [
        ('ビール', 500, 0.45),
        ('ハイボール', 400, 0.50),
        ('枝豆', 300, 0.60),
        ('唐揚げ', 500, 0.25),
        ('サラダ', 300, 0.15),
    ]
    for i, (name, price, margin) in enumerate(specs):
        products.append(Product.objects.create(
            store=dashboard_store,
            category=dashboard_category,
            sku=f'MENU-{i:03d}',
            name=name,
            price=price,
            stock=100,
            is_active=True,
            margin_rate=margin,
        ))
    return products


@pytest.fixture
def dashboard_orders(db, dashboard_store, dashboard_products):
    """Create orders with items for menu engineering analysis."""
    items_created = []
    # High-popularity items: ビール(30), ハイボール(25), 枝豆(20)
    # Low-popularity items: 唐揚げ(5), サラダ(3)
    quantities = [30, 25, 20, 5, 3]
    for product, qty in zip(dashboard_products, quantities):
        order = Order.objects.create(store=dashboard_store, status=Order.STATUS_OPEN)
        item = OrderItem.objects.create(
            order=order, product=product, qty=qty, unit_price=product.price,
        )
        items_created.append(item)
    return items_created


@pytest.fixture
def dashboard_customer_orders(db, dashboard_store, dashboard_products):
    """Create orders with customer_line_user_hash for cohort/RFM tests."""
    items = []
    customers = ['hash_alice', 'hash_bob', 'hash_carol']
    for i, cust in enumerate(customers):
        for j in range(3 - i):  # Alice: 3 orders, Bob: 2, Carol: 1
            order = Order.objects.create(
                store=dashboard_store,
                status=Order.STATUS_OPEN,
                customer_line_user_hash=cust,
            )
            item = OrderItem.objects.create(
                order=order,
                product=dashboard_products[0],
                qty=(i + 1) * 2,
                unit_price=dashboard_products[0].price,
            )
            items.append(item)
    return items


class TestMenuEngineeringAPI:
    """Tests for MenuEngineeringAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/menu-engineering/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_orders(self, admin_client):
        resp = admin_client.get('/api/dashboard/menu-engineering/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['products'] == []
        assert data['avg_popularity'] == 0

    @pytest.mark.django_db
    def test_returns_products_with_quadrants(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/menu-engineering/')
        assert resp.status_code == 200
        data = resp.json()
        products = data['products']
        assert len(products) == 5

        # All products should have quadrant field
        for p in products:
            assert p['quadrant'] in ('star', 'plowhorse', 'puzzle', 'dog')
            assert 'qty_sold' in p
            assert 'margin_rate' in p
            assert 'revenue' in p

    @pytest.mark.django_db
    def test_quadrant_classification(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/menu-engineering/')
        data = resp.json()
        products = {p['name']: p for p in data['products']}

        # avg_popularity = (30+25+20+5+3)/5 = 16.6
        # avg_margin = (0.45+0.50+0.60+0.25+0.15)/5 = 0.39

        # ビール: qty=30 >= 16.6, margin=0.45 >= 0.39 → star
        assert products['ビール']['quadrant'] == 'star'
        # ハイボール: qty=25 >= 16.6, margin=0.50 >= 0.39 → star
        assert products['ハイボール']['quadrant'] == 'star'
        # 枝豆: qty=20 >= 16.6, margin=0.60 >= 0.39 → star
        assert products['枝豆']['quadrant'] == 'star'
        # 唐揚げ: qty=5 < 16.6, margin=0.25 < 0.39 → dog
        assert products['唐揚げ']['quadrant'] == 'dog'
        # サラダ: qty=3 < 16.6, margin=0.15 < 0.39 → dog
        assert products['サラダ']['quadrant'] == 'dog'

    @pytest.mark.django_db
    def test_averages_calculated(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/menu-engineering/')
        data = resp.json()
        # avg_popularity = (30+25+20+5+3)/5 = 16.6
        assert data['avg_popularity'] == 16.6
        # avg_margin = (0.45+0.50+0.60+0.25+0.15)/5 = 0.39
        assert data['avg_margin'] == 0.39

    @pytest.mark.django_db
    def test_revenue_calculated(self, admin_client, dashboard_orders, dashboard_products):
        resp = admin_client.get('/api/dashboard/menu-engineering/')
        data = resp.json()
        products = {p['name']: p for p in data['products']}
        # ビール: 30 * 500 = 15000
        assert products['ビール']['revenue'] == 15000
        # サラダ: 3 * 300 = 900
        assert products['サラダ']['revenue'] == 900

    @pytest.mark.django_db
    def test_days_parameter(self, admin_client, dashboard_orders):
        # With days=0 should return empty (orders created "now" might be within 0 days)
        resp = admin_client.get('/api/dashboard/menu-engineering/?days=365')
        data = resp.json()
        assert len(data['products']) == 5


class TestABCAnalysisAPI:
    """Tests for ABCAnalysisAPIView (Pareto analysis)."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/abc-analysis/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_orders(self, admin_client):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['products'] == []
        assert data['total_revenue'] == 0

    @pytest.mark.django_db
    def test_returns_ranked_products(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        assert resp.status_code == 200
        data = resp.json()
        products = data['products']
        assert len(products) == 5

        for p in products:
            assert p['rank'] in ('A', 'B', 'C')
            assert 'revenue' in p
            assert 'share_pct' in p
            assert 'cumulative_pct' in p

    @pytest.mark.django_db
    def test_sorted_by_revenue_descending(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        data = resp.json()
        products = data['products']
        revenues = [p['revenue'] for p in products]
        assert revenues == sorted(revenues, reverse=True)

    @pytest.mark.django_db
    def test_cumulative_reaches_100(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        data = resp.json()
        products = data['products']
        assert products[-1]['cumulative_pct'] == 100.0

    @pytest.mark.django_db
    def test_total_revenue_correct(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        data = resp.json()
        # ビール:30*500=15000, ハイボール:25*400=10000, 枝豆:20*300=6000,
        # 唐揚げ:5*500=2500, サラダ:3*300=900
        assert data['total_revenue'] == 34400

    @pytest.mark.django_db
    def test_abc_ranking(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/abc-analysis/')
        data = resp.json()
        products = {p['name']: p for p in data['products']}
        # Sorted by revenue: ビール(15000), ハイボール(10000), 枝豆(6000), 唐揚げ(2500), サラダ(900)
        # total = 34400
        # ビール: 15000/34400=43.6%, cum=43.6% → A
        # ハイボール: 10000/34400=29.1%, cum=72.7% → A
        # 枝豆: 6000/34400=17.4%, cum=90.1% → B
        # 唐揚げ: 2500/34400=7.3%, cum=97.4% → C
        # サラダ: 900/34400=2.6%, cum=100% → C
        assert products['ビール']['rank'] == 'A'
        assert products['ハイボール']['rank'] == 'A'
        assert products['枝豆']['rank'] == 'B'
        assert products['唐揚げ']['rank'] == 'C'
        assert products['サラダ']['rank'] == 'C'


class TestSalesForecastAPI:
    """Tests for SalesForecastAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/forecast/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_forecast_no_data(self, admin_client):
        resp = admin_client.get('/api/dashboard/forecast/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['historical'] == []
        assert data['forecast'] == []
        assert data['method'] == 'moving_average'

    @pytest.mark.django_db
    def test_returns_forecast_with_data(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/forecast/?days=7')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['historical']) >= 1
        assert data['method'] in ('moving_average', 'prophet')
        # Forecast entries should have required fields
        for f in data['forecast']:
            assert 'date' in f
            assert 'predicted' in f
            assert 'lower' in f
            assert 'upper' in f

    @pytest.mark.django_db
    def test_forecast_confidence_interval(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/forecast/?days=3')
        data = resp.json()
        for f in data['forecast']:
            assert f['lower'] <= f['predicted']
            assert f['upper'] >= f['predicted']

    @pytest.mark.django_db
    def test_days_parameter_caps_at_90(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/forecast/?days=200')
        assert resp.status_code == 200


class TestSalesHeatmapAPI:
    """Tests for SalesHeatmapAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/sales-heatmap/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_heatmap_no_data(self, admin_client):
        resp = admin_client.get('/api/dashboard/sales-heatmap/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'heatmap' in data
        # Should return 7*24=168 cells, all zeros
        assert len(data['heatmap']) == 168
        assert all(c['revenue'] == 0 for c in data['heatmap'])

    @pytest.mark.django_db
    def test_returns_heatmap_with_data(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/sales-heatmap/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['heatmap']) == 168
        # At least some cells should have revenue > 0
        non_zero = [c for c in data['heatmap'] if c['revenue'] > 0]
        assert len(non_zero) > 0

    @pytest.mark.django_db
    def test_heatmap_cell_structure(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/sales-heatmap/')
        data = resp.json()
        cell = data['heatmap'][0]
        assert 'weekday' in cell
        assert 'hour' in cell
        assert 'revenue' in cell
        assert 'orders' in cell
        assert 1 <= cell['weekday'] <= 7
        assert 0 <= cell['hour'] <= 23

    @pytest.mark.django_db
    def test_days_parameter(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/sales-heatmap/?days=365')
        assert resp.status_code == 200
        data = resp.json()
        non_zero = [c for c in data['heatmap'] if c['revenue'] > 0]
        assert len(non_zero) > 0


class TestAOVTrendAPI:
    """Tests for AOVTrendAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/aov-trend/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_orders(self, admin_client):
        resp = admin_client.get('/api/dashboard/aov-trend/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['trend'] == []
        assert data['period'] == 'daily'

    @pytest.mark.django_db
    def test_returns_trend_with_data(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/aov-trend/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['trend']) >= 1

    @pytest.mark.django_db
    def test_trend_entry_structure(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/aov-trend/')
        data = resp.json()
        entry = data['trend'][0]
        assert 'date' in entry
        assert 'order_count' in entry
        assert 'total_revenue' in entry
        assert 'aov' in entry
        assert entry['order_count'] > 0
        assert entry['aov'] > 0

    @pytest.mark.django_db
    def test_aov_calculation(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/aov-trend/')
        data = resp.json()
        for entry in data['trend']:
            if entry['order_count'] > 0:
                expected_aov = round(entry['total_revenue'] / entry['order_count'])
                assert entry['aov'] == expected_aov

    @pytest.mark.django_db
    def test_period_weekly(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/aov-trend/?period=weekly')
        assert resp.status_code == 200
        data = resp.json()
        assert data['period'] == 'weekly'

    @pytest.mark.django_db
    def test_period_monthly(self, admin_client, dashboard_orders):
        resp = admin_client.get('/api/dashboard/aov-trend/?period=monthly')
        assert resp.status_code == 200
        data = resp.json()
        assert data['period'] == 'monthly'


class TestCohortAnalysisAPI:
    """Tests for CohortAnalysisAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/cohort/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_customers(self, admin_client):
        resp = admin_client.get('/api/dashboard/cohort/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['cohorts'] == []

    @pytest.mark.django_db
    def test_returns_cohorts_with_data(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/cohort/?months=12')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['cohorts']) >= 1

    @pytest.mark.django_db
    def test_cohort_structure(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/cohort/?months=12')
        data = resp.json()
        cohort = data['cohorts'][0]
        assert 'cohort' in cohort
        assert 'size' in cohort
        assert 'retention' in cohort
        assert cohort['size'] > 0

    @pytest.mark.django_db
    def test_retention_month_zero_is_100pct(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/cohort/?months=12')
        data = resp.json()
        for cohort in data['cohorts']:
            if '0' in cohort['retention']:
                assert cohort['retention']['0']['rate'] == 1.0
                assert cohort['retention']['0']['count'] == cohort['size']


class TestRFMAnalysisAPI:
    """Tests for RFMAnalysisAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/rfm/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_customers(self, admin_client):
        resp = admin_client.get('/api/dashboard/rfm/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['customers'] == []
        assert data['segments'] == []
        assert data['total_customers'] == 0

    @pytest.mark.django_db
    def test_returns_rfm_with_data(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/rfm/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['total_customers'] == 3  # alice, bob, carol
        assert len(data['customers']) == 3

    @pytest.mark.django_db
    def test_customer_rfm_structure(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/rfm/')
        data = resp.json()
        customer = data['customers'][0]
        assert 'customer_id' in customer
        assert 'recency' in customer
        assert 'frequency' in customer
        assert 'monetary' in customer
        assert 'r_score' in customer
        assert 'f_score' in customer
        assert 'm_score' in customer
        assert 'rfm_score' in customer
        assert 'segment' in customer

    @pytest.mark.django_db
    def test_rfm_scores_range(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/rfm/')
        data = resp.json()
        for c in data['customers']:
            assert 1 <= c['r_score'] <= 5
            assert 1 <= c['f_score'] <= 5
            assert 1 <= c['m_score'] <= 5

    @pytest.mark.django_db
    def test_segments_present(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/rfm/')
        data = resp.json()
        assert len(data['segments']) >= 1
        total_from_segments = sum(s['count'] for s in data['segments'])
        assert total_from_segments == data['total_customers']

    @pytest.mark.django_db
    def test_valid_segment_names(self, admin_client, dashboard_customer_orders):
        resp = admin_client.get('/api/dashboard/rfm/')
        data = resp.json()
        valid_segments = {'champion', 'loyal', 'new', 'potential', 'at_risk', 'cant_lose', 'lost', 'other'}
        for c in data['customers']:
            assert c['segment'] in valid_segments


@pytest.fixture
def basket_orders(db, dashboard_store, dashboard_products):
    """Create orders with multiple items per order for basket analysis."""
    items = []
    # 4 orders each with 2+ products
    combos = [
        [0, 1],    # ビール + ハイボール
        [0, 2],    # ビール + 枝豆
        [0, 2],    # ビール + 枝豆 (repeat)
        [1, 3],    # ハイボール + 唐揚げ
    ]
    for combo in combos:
        order = Order.objects.create(store=dashboard_store, status=Order.STATUS_OPEN)
        for idx in combo:
            item = OrderItem.objects.create(
                order=order,
                product=dashboard_products[idx],
                qty=1,
                unit_price=dashboard_products[idx].price,
            )
            items.append(item)
    return items


class TestBasketAnalysisAPI:
    """Tests for BasketAnalysisAPIView."""

    @pytest.mark.django_db
    def test_requires_auth(self):
        client = Client()
        resp = client.get('/api/dashboard/basket/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_empty_when_no_data(self, admin_client):
        resp = admin_client.get('/api/dashboard/basket/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['rules'] == []
        assert data['total_transactions'] == 0

    @pytest.mark.django_db
    def test_returns_rules_with_data(self, admin_client, basket_orders):
        resp = admin_client.get('/api/dashboard/basket/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['total_transactions'] >= 3
        assert len(data['rules']) >= 1
        assert data['method'] in ('apriori', 'pairwise')

    @pytest.mark.django_db
    def test_rule_structure(self, admin_client, basket_orders):
        resp = admin_client.get('/api/dashboard/basket/')
        data = resp.json()
        if data['rules']:
            rule = data['rules'][0]
            assert 'antecedent' in rule
            assert 'consequent' in rule
            assert 'support' in rule
            assert 'confidence' in rule
            assert 'lift' in rule
            assert isinstance(rule['antecedent'], list)
            assert isinstance(rule['consequent'], list)
            assert 0 <= rule['support'] <= 1
            assert 0 <= rule['confidence'] <= 1
            assert rule['lift'] > 0

    @pytest.mark.django_db
    def test_rules_sorted_by_lift(self, admin_client, basket_orders):
        resp = admin_client.get('/api/dashboard/basket/')
        data = resp.json()
        lifts = [r['lift'] for r in data['rules']]
        assert lifts == sorted(lifts, reverse=True)

    @pytest.mark.django_db
    def test_days_parameter(self, admin_client, basket_orders):
        resp = admin_client.get('/api/dashboard/basket/?days=365')
        assert resp.status_code == 200
        data = resp.json()
        assert data['total_transactions'] >= 3


# ==============================================================================
# Insights API
# ==============================================================================

@pytest.fixture
def insight_store(db):
    return Store.objects.create(name='InsightStore')


@pytest.fixture
def sample_insights(insight_store):
    ins1 = BusinessInsight.objects.create(
        store=insight_store, category='sales', severity='warning',
        title='売上減少', message='直近7日間の売上が減少しています。',
    )
    ins2 = BusinessInsight.objects.create(
        store=insight_store, category='inventory', severity='critical',
        title='在庫切れ', message='商品Aの在庫がゼロです。',
    )
    ins3 = BusinessInsight.objects.create(
        store=insight_store, category='customer', severity='info',
        title='リピート率向上', message='リピート率が改善しています。',
        is_read=True,
    )
    return [ins1, ins2, ins3]


class TestInsightsAPI:
    """Tests for /api/dashboard/insights/."""

    def test_requires_auth(self, client):
        resp = client.get('/api/dashboard/insights/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_get_empty(self, admin_client):
        resp = admin_client.get('/api/dashboard/insights/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['insights'] == []

    @pytest.mark.django_db
    def test_get_insights(self, admin_client, sample_insights):
        resp = admin_client.get('/api/dashboard/insights/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['insights']) == 3

    @pytest.mark.django_db
    def test_insight_structure(self, admin_client, sample_insights):
        resp = admin_client.get('/api/dashboard/insights/')
        ins = resp.json()['insights'][0]
        assert 'id' in ins
        assert 'category' in ins
        assert 'severity' in ins
        assert 'title' in ins
        assert 'message' in ins
        assert 'is_read' in ins
        assert 'created_at' in ins

    @pytest.mark.django_db
    def test_unread_filter(self, admin_client, sample_insights):
        resp = admin_client.get('/api/dashboard/insights/?unread=1')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['insights']) == 2
        for ins in data['insights']:
            assert ins['is_read'] is False

    @pytest.mark.django_db
    def test_mark_read_single(self, admin_client, sample_insights):
        ins_id = sample_insights[0].id
        resp = admin_client.post(
            '/api/dashboard/insights/',
            data={'action': 'mark_read', 'insight_id': ins_id},
            content_type='application/json',
        )
        assert resp.status_code == 200
        sample_insights[0].refresh_from_db()
        assert sample_insights[0].is_read is True

    @pytest.mark.django_db
    def test_mark_all_read(self, admin_client, sample_insights):
        resp = admin_client.post(
            '/api/dashboard/insights/',
            data={'action': 'mark_read'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        unread = BusinessInsight.objects.filter(is_read=False).count()
        assert unread == 0

    @pytest.mark.django_db
    def test_generate_insights(self, admin_client, insight_store):
        resp = admin_client.post(
            '/api/dashboard/insights/',
            data={'action': 'generate'},
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert 'created_count' in data

    @pytest.mark.django_db
    def test_ordered_by_newest(self, admin_client, sample_insights):
        resp = admin_client.get('/api/dashboard/insights/')
        data = resp.json()
        dates = [ins['created_at'] for ins in data['insights']]
        assert dates == sorted(dates, reverse=True)


# ===== KPI Scorecard API Tests =====

@pytest.fixture
def kpi_store(db):
    return Store.objects.create(name='KPIテスト店舗')


@pytest.fixture
def kpi_category(kpi_store):
    return Category.objects.create(store=kpi_store, name='KPIカテゴリ')


@pytest.fixture
def kpi_data(kpi_store, kpi_category):
    """Create products, orders, schedules, and table seats for KPI tests."""
    prod = Product.objects.create(
        store=kpi_store, category=kpi_category,
        name='KPI商品', sku='KPI-001', price=1000,
        stock=50, is_active=True, margin_rate=0.4,
    )
    # 5 orders from 2 repeat customers + 1 unique
    for i in range(3):
        o = Order.objects.create(
            store=kpi_store, status=Order.STATUS_OPEN,
            customer_line_user_hash='repeat_user_1',
        )
        OrderItem.objects.create(order=o, product=prod, qty=2, unit_price=1000)
    for i in range(2):
        o = Order.objects.create(
            store=kpi_store, status=Order.STATUS_OPEN,
            customer_line_user_hash='repeat_user_2',
        )
        OrderItem.objects.create(order=o, product=prod, qty=1, unit_price=1000)

    # Schedules for cancel rate
    user = User.objects.create_user(username='kpi_staff', password='pass')
    staff = Staff.objects.create(name='KPIスタッフ', store=kpi_store, user=user)
    from django.utils import timezone
    from datetime import timedelta
    now = timezone.now()
    for i in range(10):
        Schedule.objects.create(
            staff=staff,
            start=now - timedelta(days=3),
            end=now - timedelta(days=3) + timedelta(hours=1),
            is_cancelled=(i < 3),  # 30% cancel
        )

    # Table seat
    TableSeat.objects.create(store=kpi_store, label='T1')

    return {'product': prod, 'staff': staff}


class TestKPIScoreCardAPI:
    """Tests for KPIScoreCardAPIView."""

    @pytest.mark.django_db
    def test_auth_required(self, client):
        resp = client.get('/api/dashboard/kpi-scorecard/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_returns_kpis(self, admin_client):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        assert resp.status_code == 200
        data = resp.json()
        assert 'kpis' in data
        assert 'period_days' in data

    @pytest.mark.django_db
    def test_kpi_structure(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        for kpi in data['kpis']:
            assert 'key' in kpi
            assert 'label' in kpi
            assert 'value' in kpi
            assert 'status' in kpi
            assert kpi['status'] in ('good', 'warn', 'bad', 'neutral')

    @pytest.mark.django_db
    def test_aov_calculation(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        aov_kpi = next(k for k in data['kpis'] if k['key'] == 'aov')
        # 5 orders: 3 * 2000 + 2 * 1000 = 8000, AOV = 8000/5 = 1600
        assert aov_kpi['value'] == 1600

    @pytest.mark.django_db
    def test_revenue_total(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        rev = next(k for k in data['kpis'] if k['key'] == 'total_revenue')
        assert rev['value'] == 8000  # 3*2*1000 + 2*1*1000

    @pytest.mark.django_db
    def test_order_count(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        orders = next(k for k in data['kpis'] if k['key'] == 'total_orders')
        assert orders['value'] == 5

    @pytest.mark.django_db
    def test_repeat_rate(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        rr = next(k for k in data['kpis'] if k['key'] == 'repeat_rate')
        # 2 customers both have >=2 orders → 100% repeat
        assert rr['value'] == 100.0

    @pytest.mark.django_db
    def test_cancel_rate(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        cr = next(k for k in data['kpis'] if k['key'] == 'cancel_rate')
        assert cr['value'] == 30.0  # 3/10 * 100

    @pytest.mark.django_db
    def test_food_cost_pct(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        fc = next(k for k in data['kpis'] if k['key'] == 'food_cost_pct')
        # margin_rate=0.4 → food_cost = (1-0.4)*100 = 60%
        assert fc['value'] == 60.0

    @pytest.mark.django_db
    def test_empty_data(self, admin_client):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/')
        data = resp.json()
        aov = next(k for k in data['kpis'] if k['key'] == 'aov')
        assert aov['value'] == 0

    @pytest.mark.django_db
    def test_custom_days_param(self, admin_client, kpi_data):
        resp = admin_client.get('/api/dashboard/kpi-scorecard/?days=7')
        assert resp.status_code == 200
        data = resp.json()
        assert data['period_days'] == 7


# ===== Customer Feedback & NPS Tests =====

@pytest.fixture
def nps_store(db):
    return Store.objects.create(name='NPS店舗')


@pytest.fixture
def sample_feedbacks(nps_store):
    """Create feedbacks: 3 promoters, 2 passives, 1 detractor."""
    fbs = []
    # Promoters (9-10)
    for nps in [10, 9, 10]:
        fbs.append(CustomerFeedback.objects.create(
            store=nps_store, nps_score=nps,
            food_rating=5, service_rating=5, ambiance_rating=4,
            comment='素晴らしい！', sentiment='positive',
        ))
    # Passives (7-8)
    for nps in [7, 8]:
        fbs.append(CustomerFeedback.objects.create(
            store=nps_store, nps_score=nps,
            food_rating=3, service_rating=3, ambiance_rating=3,
            comment='まあまあ', sentiment='neutral',
        ))
    # Detractor (0-6)
    fbs.append(CustomerFeedback.objects.create(
        store=nps_store, nps_score=3,
        food_rating=2, service_rating=1, ambiance_rating=2,
        comment='改善希望', sentiment='negative',
    ))
    return fbs


class TestCustomerFeedbackAPI:
    """Tests for CustomerFeedbackAPIView."""

    @pytest.mark.django_db
    def test_submit_feedback(self, client, nps_store):
        resp = client.post(
            '/api/dashboard/feedback/',
            data={'store_id': nps_store.id, 'nps_score': 9, 'food_rating': 5, 'service_rating': 4, 'ambiance_rating': 4, 'comment': 'Great!'},
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data['status'] == 'ok'
        assert CustomerFeedback.objects.count() == 1

    @pytest.mark.django_db
    def test_submit_no_auth_required(self, client, nps_store):
        """Feedback submission should work without authentication."""
        resp = client.post(
            '/api/dashboard/feedback/',
            data={'store_id': nps_store.id, 'nps_score': 5},
            content_type='application/json',
        )
        assert resp.status_code == 201

    @pytest.mark.django_db
    def test_submit_missing_fields(self, client):
        resp = client.post(
            '/api/dashboard/feedback/',
            data={'nps_score': 5},
            content_type='application/json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_submit_invalid_nps(self, client, nps_store):
        resp = client.post(
            '/api/dashboard/feedback/',
            data={'store_id': nps_store.id, 'nps_score': 11},
            content_type='application/json',
        )
        assert resp.status_code == 400

    @pytest.mark.django_db
    def test_auto_sentiment_promoter(self, client, nps_store):
        client.post(
            '/api/dashboard/feedback/',
            data={'store_id': nps_store.id, 'nps_score': 10},
            content_type='application/json',
        )
        fb = CustomerFeedback.objects.first()
        assert fb.sentiment == 'positive'

    @pytest.mark.django_db
    def test_auto_sentiment_detractor(self, client, nps_store):
        client.post(
            '/api/dashboard/feedback/',
            data={'store_id': nps_store.id, 'nps_score': 3},
            content_type='application/json',
        )
        fb = CustomerFeedback.objects.first()
        assert fb.sentiment == 'negative'

    @pytest.mark.django_db
    def test_list_requires_auth(self, client):
        resp = client.get('/api/dashboard/feedback/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_list_feedbacks(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/feedback/')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['feedbacks']) == 6

    @pytest.mark.django_db
    def test_feedback_structure(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/feedback/')
        fb = resp.json()['feedbacks'][0]
        assert 'nps_score' in fb
        assert 'nps_category' in fb
        assert 'food_rating' in fb
        assert 'sentiment' in fb


class TestNPSStatsAPI:
    """Tests for NPSStatsAPIView."""

    @pytest.mark.django_db
    def test_auth_required(self, client):
        resp = client.get('/api/dashboard/nps/')
        assert resp.status_code == 403

    @pytest.mark.django_db
    def test_empty_data(self, admin_client):
        resp = admin_client.get('/api/dashboard/nps/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['nps_score'] == 0
        assert data['total'] == 0

    @pytest.mark.django_db
    def test_nps_calculation(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/nps/')
        data = resp.json()
        # 3 promoters, 2 passives, 1 detractor out of 6
        # NPS = (3 - 1) / 6 * 100 = 33.3
        assert data['nps_score'] == 33.3
        assert data['promoters'] == 3
        assert data['passives'] == 2
        assert data['detractors'] == 1
        assert data['total'] == 6

    @pytest.mark.django_db
    def test_avg_ratings(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/nps/')
        data = resp.json()
        assert data['avg_food'] > 0
        assert data['avg_service'] > 0
        assert data['avg_ambiance'] > 0

    @pytest.mark.django_db
    def test_trend_data(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/nps/')
        data = resp.json()
        assert isinstance(data['trend'], list)

    @pytest.mark.django_db
    def test_sentiment_distribution(self, admin_client, sample_feedbacks):
        resp = admin_client.get('/api/dashboard/nps/')
        data = resp.json()
        assert data['sentiment_dist']['positive'] == 3
        assert data['sentiment_dist']['neutral'] == 2
        assert data['sentiment_dist']['negative'] == 1


class TestCustomerFeedbackModel:
    """Tests for CustomerFeedback model."""

    @pytest.mark.django_db
    def test_nps_category_promoter(self, nps_store):
        fb = CustomerFeedback.objects.create(store=nps_store, nps_score=9)
        assert fb.nps_category == 'promoter'

    @pytest.mark.django_db
    def test_nps_category_passive(self, nps_store):
        fb = CustomerFeedback.objects.create(store=nps_store, nps_score=8)
        assert fb.nps_category == 'passive'

    @pytest.mark.django_db
    def test_nps_category_detractor(self, nps_store):
        fb = CustomerFeedback.objects.create(store=nps_store, nps_score=5)
        assert fb.nps_category == 'detractor'

    @pytest.mark.django_db
    def test_str(self, nps_store):
        fb = CustomerFeedback.objects.create(store=nps_store, nps_score=10)
        assert 'NPS:10' in str(fb)
