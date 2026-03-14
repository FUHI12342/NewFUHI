"""
Phase 2: ダッシュボードAPI ビューのテスト

対象 (views_restaurant_dashboard.py):
  - DashboardLayoutAPIView (GET/PUT)
  - ReservationStatsAPIView (GET)
  - SalesStatsAPIView (GET)
  - StaffPerformanceAPIView (GET)
  - ShiftSummaryAPIView (GET)
  - LowStockAlertAPIView (GET)
  - VisitorForecastAPIView (GET)
  - CLVAnalysisAPIView (GET)
  - AutoOrderRecommendationAPIView (GET)
  - ExternalDataAPIView (GET)
"""
import json
import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from booking.models import (
    Store, Staff, Schedule, Order, OrderItem, Product, Category,
    DashboardLayout, DEFAULT_DASHBOARD_LAYOUT,
    ShiftPeriod, ShiftAssignment, VisitorCount,
)

User = get_user_model()


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_d(db):
    return Store.objects.create(
        name="ダッシュボード店舗", address="東京", business_hours="10-22",
        nearest_station="渋谷",
    )


@pytest.fixture
def admin_dash(store_d):
    """Superuser with staff profile and logged-in client."""
    user = User.objects.create_superuser(
        username="dash_admin", password="pass123", email="dadmin@test.com",
    )
    Staff.objects.create(name="管理者", store=store_d, user=user)
    client = Client()
    client.login(username="dash_admin", password="pass123")
    return client


@pytest.fixture
def staff_dash(store_d):
    """Regular staff user with logged-in client."""
    user = User.objects.create_user(
        username="dash_staff", password="pass123", email="dstaff@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="スタッフ", store=store_d, user=user)
    client = Client()
    client.login(username="dash_staff", password="pass123")
    return client


@pytest.fixture
def anon_client():
    return Client()


@pytest.fixture
def sample_schedule(store_d):
    """Create a confirmed schedule for stats."""
    staff_user = User.objects.create_user(
        username="sched_staff", password="pass123", email="sched@test.com",
    )
    s = Staff.objects.create(name="予約スタッフ", store=store_d, user=staff_user)
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=2),
        staff=s,
        is_temporary=False,
        is_cancelled=False,
    )


@pytest.fixture
def sample_order_data(store_d):
    """Create products and orders for sales/stock tests."""
    cat = Category.objects.create(store=store_d, name="テストカテゴリ", sort_order=0)
    p1 = Product.objects.create(
        store=store_d, category=cat, sku="D001",
        name="商品1", price=500, stock=3, low_stock_threshold=5, is_active=True,
    )
    p2 = Product.objects.create(
        store=store_d, category=cat, sku="D002",
        name="商品2", price=1000, stock=100, low_stock_threshold=10, is_active=True,
    )
    order = Order.objects.create(store=store_d, status=Order.STATUS_OPEN)
    OrderItem.objects.create(
        order=order, product=p1, qty=2, unit_price=p1.price,
        status=OrderItem.STATUS_ORDERED,
    )
    OrderItem.objects.create(
        order=order, product=p2, qty=1, unit_price=p2.price,
        status=OrderItem.STATUS_ORDERED,
    )
    return p1, p2, order


# ==============================
# DashboardLayoutAPIView
# ==============================

class TestDashboardLayoutAPI:
    """GET/PUT /api/dashboard/layout/"""
    URL = '/api/dashboard/layout/'

    def test_get_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_get_default_layout(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['layout'] == DEFAULT_DASHBOARD_LAYOUT

    def test_get_saved_layout(self, admin_dash):
        user = User.objects.get(username="dash_admin")
        custom = [{"id": "custom", "x": 0, "y": 0, "w": 12, "h": 6}]
        DashboardLayout.objects.create(user=user, layout_json=custom)
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()['layout'] == custom

    def test_put_creates_layout(self, admin_dash):
        new_layout = [{"id": "test", "x": 0, "y": 0, "w": 6, "h": 3}]
        resp = admin_dash.put(
            self.URL, json.dumps({'layout': new_layout}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        user = User.objects.get(username="dash_admin")
        assert DashboardLayout.objects.get(user=user).layout_json == new_layout

    def test_put_updates_layout(self, admin_dash):
        user = User.objects.get(username="dash_admin")
        DashboardLayout.objects.create(user=user, layout_json=[])
        new_layout = [{"id": "updated"}]
        resp = admin_dash.put(
            self.URL, json.dumps({'layout': new_layout}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert DashboardLayout.objects.get(user=user).layout_json == new_layout

    def test_put_unauthenticated(self, anon_client):
        resp = anon_client.put(
            self.URL, json.dumps({'layout': []}),
            content_type='application/json',
        )
        assert resp.status_code == 403


# ==============================
# ReservationStatsAPIView
# ==============================

class TestReservationStatsAPI:
    """GET /api/dashboard/reservations/"""
    URL = '/api/dashboard/reservations/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['daily'] == []
        assert data['future_count'] == 0
        assert data['cancel_rate'] == 0

    def test_with_schedule(self, admin_dash, sample_schedule):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['future_count'] >= 1

    def test_staff_access(self, staff_dash, sample_schedule):
        resp = staff_dash.get(self.URL)
        assert resp.status_code == 200


# ==============================
# SalesStatsAPIView
# ==============================

class TestSalesStatsAPI:
    """GET /api/dashboard/sales/"""
    URL = '/api/dashboard/sales/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['trend'] == []
        assert data['top_products'] == []

    def test_with_orders(self, admin_dash, sample_order_data):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['trend']) >= 1
        assert len(data['top_products']) >= 1

    def test_period_param(self, admin_dash, sample_order_data):
        resp = admin_dash.get(self.URL + '?period=weekly')
        assert resp.status_code == 200

    def test_staff_access(self, staff_dash, sample_order_data):
        resp = staff_dash.get(self.URL)
        assert resp.status_code == 200


# ==============================
# StaffPerformanceAPIView
# ==============================

class TestStaffPerformanceAPI:
    """GET /api/dashboard/staff-performance/"""
    URL = '/api/dashboard/staff-performance/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash, store_d):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert 'staff' in data

    def test_with_reservations(self, admin_dash, sample_schedule):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['staff']) >= 1


# ==============================
# ShiftSummaryAPIView
# ==============================

class TestShiftSummaryAPI:
    """GET /api/dashboard/shift-summary/"""
    URL = '/api/dashboard/shift-summary/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['total_assignments'] == 0
        assert data['open_periods'] == 0

    def test_with_shift_data(self, admin_dash, store_d):
        staff_user = User.objects.get(username="dash_admin")
        s = Staff.objects.get(user=staff_user)
        period = ShiftPeriod.objects.create(
            store=store_d, year_month=date.today().replace(day=1),
            deadline=timezone.now() + timedelta(days=7),
            status='open', created_by=s,
        )
        ShiftAssignment.objects.create(
            period=period, staff=s, date=date.today(),
            start_hour=9, end_hour=17,
        )
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['total_assignments'] >= 1
        assert data['open_periods'] >= 1


# ==============================
# LowStockAlertAPIView
# ==============================

class TestLowStockAlertAPI:
    """GET /api/dashboard/low-stock/"""
    URL = '/api/dashboard/low-stock/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_no_low_stock(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        assert resp.json()['products'] == []

    def test_with_low_stock(self, admin_dash, sample_order_data):
        """p1 has stock=3, threshold=5 → should appear."""
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        products = resp.json()['products']
        assert len(products) >= 1
        assert products[0]['name'] == '商品1'
        assert products[0]['stock'] == 3


# ==============================
# VisitorForecastAPIView
# ==============================

class TestVisitorForecastAPI:
    """GET /api/dashboard/visitor-forecast/"""
    URL = '/api/dashboard/visitor-forecast/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert 'forecast' in data

    def test_with_days_param(self, admin_dash):
        resp = admin_dash.get(self.URL + '?days=7')
        assert resp.status_code == 200
        data = resp.json()
        assert len(data['forecast']) == 7

    def test_with_visitor_data(self, admin_dash, store_d):
        today = timezone.now().date()
        for i in range(7):
            d = today - timedelta(days=i)
            VisitorCount.objects.create(
                store=store_d, date=d, hour=12,
                pir_count=20, estimated_visitors=10, order_count=5,
            )
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200


# ==============================
# CLVAnalysisAPIView
# ==============================

class TestCLVAnalysisAPI:
    """GET /api/dashboard/clv/"""
    URL = '/api/dashboard/clv/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['summary']['total_customers'] == 0

    def test_with_months_param(self, admin_dash):
        resp = admin_dash.get(self.URL + '?months=3')
        assert resp.status_code == 200


# ==============================
# AutoOrderRecommendationAPIView
# ==============================

class TestAutoOrderAPI:
    """GET /api/dashboard/auto-order/"""
    URL = '/api/dashboard/auto-order/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_empty_data(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['summary']['total_products'] == 0

    def test_with_products(self, admin_dash, sample_order_data):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert data['summary']['total_products'] >= 1


# ==============================
# ExternalDataAPIView
# ==============================

class TestExternalDataAPI:
    """GET /api/dashboard/external-data/"""
    URL = '/api/dashboard/external-data/'

    def test_unauthenticated(self, anon_client):
        resp = anon_client.get(self.URL)
        assert resp.status_code == 403

    def test_default_status(self, admin_dash):
        resp = admin_dash.get(self.URL)
        assert resp.status_code == 200
        data = resp.json()
        assert 'integrations' in data
        assert data['total'] == 2

    def test_weather_service(self, admin_dash):
        resp = admin_dash.get(self.URL + '?service=weather')
        assert resp.status_code == 200
        data = resp.json()
        assert data['is_mock'] is True
        assert 'forecast' in data

    def test_weather_with_coords(self, admin_dash):
        resp = admin_dash.get(self.URL + '?service=weather&lat=34.0&lng=135.0&days=3')
        assert resp.status_code == 200
        data = resp.json()
        assert data['location']['lat'] == 34.0

    def test_weather_invalid_coords(self, admin_dash):
        resp = admin_dash.get(self.URL + '?service=weather&lat=invalid&lng=bad')
        assert resp.status_code == 200
        data = resp.json()
        # Falls back to default Tokyo coords
        assert data['location']['lat'] == 35.6762

    def test_google_reviews_service(self, admin_dash):
        resp = admin_dash.get(self.URL + '?service=google_reviews')
        assert resp.status_code == 200
        data = resp.json()
        assert data['is_mock'] is True
        assert 'reviews' in data

    def test_google_reviews_with_place_id(self, admin_dash):
        resp = admin_dash.get(self.URL + '?service=google_reviews&place_id=ChIJtest')
        assert resp.status_code == 200
        assert resp.json()['place_id'] == 'ChIJtest'
