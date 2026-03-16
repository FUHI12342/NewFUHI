"""
Tests for booking/views_inventory.py — InventoryDashboardView & StockInFormView.
"""
import pytest
from django.test import Client
from django.contrib.auth import get_user_model

from booking.models import (
    Store, Staff, Category, Product, StockMovement,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ═════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════

@pytest.fixture
def inv_store(db):
    return Store.objects.create(name="在庫テスト店舗", address="東京都")


@pytest.fixture
def inv_admin(db, inv_store):
    user = User.objects.create_superuser(
        username="inv_admin", password="pass1234", email="inv@test.com",
    )
    Staff.objects.create(name="管理者", store=inv_store, user=user, is_developer=True)
    client = Client()
    client.login(username="inv_admin", password="pass1234")
    return client


@pytest.fixture
def inv_staff_client(db, inv_store):
    user = User.objects.create_user(
        username="inv_staff", password="pass1234", email="staff@test.com",
        is_staff=True,
    )
    Staff.objects.create(name="スタッフ", store=inv_store, user=user)
    client = Client()
    client.login(username="inv_staff", password="pass1234")
    return client


@pytest.fixture
def ec_category(db, inv_store):
    return Category.objects.create(
        store=inv_store, name="ECカテゴリ", sort_order=0,
        is_restaurant_menu=False,
    )


@pytest.fixture
def restaurant_category(db, inv_store):
    return Category.objects.create(
        store=inv_store, name="飲食カテゴリ", sort_order=1,
        is_restaurant_menu=True,
    )


@pytest.fixture
def ec_product(db, inv_store, ec_category):
    return Product.objects.create(
        store=inv_store, category=ec_category,
        sku="EC-001", name="ECテスト商品", price=1000,
        stock=50, low_stock_threshold=10, is_active=True,
    )


@pytest.fixture
def restaurant_product(db, inv_store, restaurant_category):
    return Product.objects.create(
        store=inv_store, category=restaurant_category,
        sku="REST-001", name="飲食テスト商品", price=800,
        stock=5, low_stock_threshold=10, is_active=True,
    )


@pytest.fixture
def out_of_stock_product(db, inv_store, ec_category):
    return Product.objects.create(
        store=inv_store, category=ec_category,
        sku="EC-002", name="在庫切れ商品", price=500,
        stock=0, low_stock_threshold=5, is_active=True,
    )


# ═════════════════════════════════════════════
# InventoryDashboardView
# ═════════════════════════════════════════════

class TestInventoryDashboardView:
    URL = "/admin/inventory/"

    def test_dashboard_loads(self, inv_admin, ec_product, restaurant_product):
        resp = inv_admin.get(self.URL)
        assert resp.status_code == 200
        assert "在庫管理" in resp.content.decode()

    def test_dashboard_shows_products(self, inv_admin, ec_product, restaurant_product):
        resp = inv_admin.get(self.URL)
        content = resp.content.decode()
        assert ec_product.name in content
        assert restaurant_product.name in content

    def test_filter_ec_only(self, inv_admin, ec_product, restaurant_product):
        resp = inv_admin.get(self.URL + "?category=ec")
        ctx = resp.context
        product_names = [p.name for p in ctx['products']]
        assert ec_product.name in product_names
        assert restaurant_product.name not in product_names
        assert ctx['category_filter'] == 'ec'

    def test_filter_restaurant_only(self, inv_admin, ec_product, restaurant_product):
        resp = inv_admin.get(self.URL + "?category=restaurant")
        ctx = resp.context
        product_names = [p.name for p in ctx['products']]
        assert restaurant_product.name in product_names
        assert ec_product.name not in product_names
        assert ctx['category_filter'] == 'restaurant'

    def test_filter_all(self, inv_admin, ec_product, restaurant_product):
        resp = inv_admin.get(self.URL + "?category=all")
        ctx = resp.context
        assert ctx['category_filter'] == 'all'
        assert len(ctx['products']) == 2

    def test_filter_low_only(self, inv_admin, ec_product, restaurant_product):
        # ec_product: stock=50, threshold=10 → NOT low
        # restaurant_product: stock=5, threshold=10 → low
        resp = inv_admin.get(self.URL + "?low_only=1")
        ctx = resp.context
        assert ctx['low_only'] is True
        product_names = [p.name for p in ctx['products']]
        assert restaurant_product.name in product_names
        assert ec_product.name not in product_names

    def test_stats_counts(self, inv_admin, ec_product, restaurant_product, out_of_stock_product):
        resp = inv_admin.get(self.URL)
        ctx = resp.context
        assert ctx['total_count'] == 3
        # low stock: restaurant(5<=10) + out_of_stock(0<=5) = 2
        assert ctx['low_stock_count'] == 2
        # out of stock: 0<=0 = 1
        assert ctx['out_of_stock_count'] == 1

    def test_staff_user_can_access(self, inv_staff_client, ec_product):
        resp = inv_staff_client.get(self.URL)
        assert resp.status_code == 200

    def test_no_store_returns_empty(self, db):
        user = User.objects.create_superuser(
            username="nostore_admin", password="pass1234", email="no@test.com",
        )
        client = Client()
        client.login(username="nostore_admin", password="pass1234")
        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_combined_filters(self, inv_admin, ec_product, restaurant_product, out_of_stock_product):
        resp = inv_admin.get(self.URL + "?category=ec&low_only=1")
        ctx = resp.context
        product_names = [p.name for p in ctx['products']]
        # ec low stock: out_of_stock_product (0<=5)
        assert out_of_stock_product.name in product_names
        assert ec_product.name not in product_names
        assert restaurant_product.name not in product_names


# ═════════════════════════════════════════════
# StockInFormView
# ═════════════════════════════════════════════

class TestStockInFormView:
    URL = "/admin/inventory/stock-in/"

    def test_stock_in_success(self, inv_admin, ec_product):
        initial_stock = ec_product.stock
        resp = inv_admin.post(self.URL, {
            "product": ec_product.id,
            "quantity": 20,
            "note": "テスト入荷",
        })
        assert resp.status_code == 302  # redirect

        ec_product.refresh_from_db()
        assert ec_product.stock == initial_stock + 20

        movement = StockMovement.objects.filter(product=ec_product).last()
        assert movement is not None
        assert movement.qty == 20
        assert movement.movement_type == StockMovement.TYPE_IN

    def test_stock_in_without_note(self, inv_admin, ec_product):
        resp = inv_admin.post(self.URL, {
            "product": ec_product.id,
            "quantity": 5,
            "note": "",
        })
        assert resp.status_code == 302
        ec_product.refresh_from_db()
        assert ec_product.stock == 55  # 50 + 5

    def test_stock_in_invalid_quantity_zero(self, inv_admin, ec_product):
        resp = inv_admin.post(self.URL, {
            "product": ec_product.id,
            "quantity": 0,
            "note": "",
        })
        # form_invalid redirects
        assert resp.status_code == 302
        ec_product.refresh_from_db()
        assert ec_product.stock == 50  # unchanged

    def test_stock_in_missing_product(self, inv_admin):
        resp = inv_admin.post(self.URL, {
            "product": "",
            "quantity": 5,
            "note": "",
        })
        assert resp.status_code == 302

    def test_stock_in_staff_user(self, inv_staff_client, ec_product):
        resp = inv_staff_client.post(self.URL, {
            "product": ec_product.id,
            "quantity": 10,
            "note": "スタッフ入荷",
        })
        assert resp.status_code == 302
        ec_product.refresh_from_db()
        assert ec_product.stock == 60  # 50 + 10

        movement = StockMovement.objects.filter(product=ec_product).last()
        assert movement.by_staff is not None
        assert movement.by_staff.name == "スタッフ"


# ═════════════════════════════════════════════
# StockInForm unit tests
# ═════════════════════════════════════════════

class TestStockInForm:
    def test_form_without_store(self):
        from booking.views_inventory import StockInForm
        form = StockInForm()
        assert form.fields['product'].queryset.count() == 0

    def test_form_with_store(self, inv_store, ec_product):
        from booking.views_inventory import StockInForm
        form = StockInForm(store=inv_store)
        assert ec_product in form.fields['product'].queryset

    def test_form_valid_data(self, inv_store, ec_product):
        from booking.views_inventory import StockInForm
        form = StockInForm(
            data={"product": ec_product.id, "quantity": 10, "note": "ok"},
            store=inv_store,
        )
        assert form.is_valid()

    def test_form_invalid_negative_qty(self, inv_store, ec_product):
        from booking.views_inventory import StockInForm
        form = StockInForm(
            data={"product": ec_product.id, "quantity": -1, "note": ""},
            store=inv_store,
        )
        assert not form.is_valid()
        assert 'quantity' in form.errors

    def test_form_invalid_exceeds_max(self, inv_store, ec_product):
        from booking.views_inventory import StockInForm
        form = StockInForm(
            data={"product": ec_product.id, "quantity": 99999, "note": ""},
            store=inv_store,
        )
        assert not form.is_valid()
