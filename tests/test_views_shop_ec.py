"""
tests/test_views_shop_ec.py
EC shop views: ShopView, CartView, ShopCheckoutView, Cart APIs
(CartAddAPIView, CartUpdateAPIView, CartRemoveAPIView).
"""
import json
import pytest
from django.urls import reverse
from booking.models import Product, Category, Order, OrderItem


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


@pytest.fixture
def ec_product(db, store, category):
    """Product visible in EC shop."""
    return Product.objects.create(
        store=store,
        category=category,
        sku='EC-001',
        name='EC商品',
        price=1200,
        stock=50,
        is_active=True,
        is_ec_visible=True,
    )


# ------------------------------------------------------------------
# ShopView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestShopView:
    def test_get_returns_200(self, api_client, ec_product):
        url = reverse('booking:shop')
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_lists_ec_visible_products_only(self, api_client, ec_product, product):
        """product fixture has is_ec_visible=False by default."""
        url = reverse('booking:shop')
        resp = api_client.get(url)
        product_names = [p['name'] for p in resp.context['products']]
        assert ec_product.name in product_names
        # product (non-EC) should NOT appear
        assert product.name not in product_names

    def test_filter_by_category(self, api_client, ec_product, category):
        url = reverse('booking:shop')
        resp = api_client.get(url, {'category': category.pk})
        assert resp.status_code == 200

    def test_search_by_query(self, api_client, ec_product):
        url = reverse('booking:shop')
        resp = api_client.get(url, {'q': 'EC商品'})
        assert resp.status_code == 200
        assert len(resp.context['products']) >= 1

    def test_search_no_match(self, api_client, ec_product):
        url = reverse('booking:shop')
        resp = api_client.get(url, {'q': 'zzz_nonexistent_product'})
        assert resp.status_code == 200
        assert len(resp.context['products']) == 0


# ------------------------------------------------------------------
# CartView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCartView:
    def test_empty_cart(self, api_client):
        url = reverse('booking:shop_cart')
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['total'] == 0
        assert resp.context['cart_items'] == []

    def test_cart_with_items(self, api_client, ec_product):
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 2,
            }
        }
        session.save()
        url = reverse('booking:shop_cart')
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['total'] == ec_product.price * 2


# ------------------------------------------------------------------
# CartAddAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCartAddAPIView:
    def test_add_to_cart(self, api_client, ec_product):
        url = reverse('booking_api:cart_add_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': ec_product.id, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert data['cart_count'] == 1

    def test_add_nonexistent_product(self, api_client):
        url = reverse('booking_api:cart_add_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': 99999, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_add_insufficient_stock(self, api_client, ec_product):
        ec_product.stock = 0
        ec_product.save()
        url = reverse('booking_api:cart_add_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': ec_product.id, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------
# CartUpdateAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCartUpdateAPIView:
    def test_update_quantity(self, api_client, ec_product):
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 1,
            }
        }
        session.save()

        url = reverse('booking_api:cart_update_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': ec_product.id, 'qty': 5}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 5

    def test_update_nonexistent_product_in_cart(self, api_client):
        url = reverse('booking_api:cart_update_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': 99999, 'qty': 2}),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# CartRemoveAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCartRemoveAPIView:
    def test_remove_from_cart(self, api_client, ec_product):
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 3,
            }
        }
        session.save()

        url = reverse('booking_api:cart_remove_api')
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': ec_product.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 0


# ------------------------------------------------------------------
# ShopCheckoutView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestShopCheckoutView:
    def test_get_empty_cart_redirects(self, api_client):
        url = reverse('booking:shop_checkout')
        resp = api_client.get(url)
        assert resp.status_code == 302

    def test_get_with_cart(self, api_client, ec_product):
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 1,
            }
        }
        session.save()
        url = reverse('booking:shop_checkout')
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['total'] == ec_product.price

    def test_post_creates_order_with_stock_deduction(self, api_client, ec_product):
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 3,
            }
        }
        session.save()

        url = reverse('booking:shop_checkout')
        resp = api_client.post(url, {
            'customer_name': 'テスト太郎',
            'customer_email': 'test@example.com',
            'customer_phone': '090-1234-5678',
            'customer_address': '東京都新宿区',
        })
        assert resp.status_code == 302  # redirect to shop

        order = Order.objects.first()
        assert order is not None
        item = order.items.first()
        assert item.qty == 3

        ec_product.refresh_from_db()
        assert ec_product.stock == 47  # 50 - 3
