"""
tests/test_ec_payment.py
EC決済フロー: ECPaymentView, ECOrderConfirmationView, ShopCheckoutView redirect,
seed_ec_goods management command.
"""
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
    return Product.objects.create(
        store=store,
        category=category,
        sku='EC-PAY-001',
        name='テスト決済商品',
        price=1500,
        stock=10,
        is_active=True,
        is_ec_visible=True,
    )


@pytest.fixture
def ec_order(db, store, ec_product):
    """EC注文（未払い、OPEN状態）"""
    order = Order.objects.create(
        store=store,
        status=Order.STATUS_OPEN,
        channel='ec',
        customer_name='テスト太郎',
        customer_email='test@example.com',
        customer_phone='090-1234-5678',
        customer_address='東京都新宿区1-1-1',
        shipping_status='pending',
    )
    OrderItem.objects.create(
        order=order,
        product=ec_product,
        qty=2,
        unit_price=ec_product.price,
    )
    return order


@pytest.fixture
def paid_order(db, ec_order):
    """支払済みの注文"""
    ec_order.payment_status = 'paid'
    ec_order.status = Order.STATUS_CLOSED
    ec_order.save(update_fields=['payment_status', 'status'])
    return ec_order


VALID_CARD_DATA = {
    'card_number': '4242 4242 4242 4242',
    'card_expiry': '12/30',
    'card_cvv': '123',
    'card_name': 'TEST TARO',
}


# ------------------------------------------------------------------
# ECPaymentView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestECPaymentView:
    def test_get_shows_payment_form(self, api_client, ec_order):
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert 'order' in resp.context
        assert resp.context['total'] == ec_order.items.first().qty * ec_order.items.first().unit_price

    def test_get_redirects_without_session(self, api_client, ec_order):
        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.get(url)
        assert resp.status_code == 302
        assert reverse('booking:shop') in resp.url

    def test_get_redirects_if_already_paid(self, api_client, paid_order):
        session = api_client.session
        session['ec_pending_order_id'] = paid_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': paid_order.id})
        resp = api_client.get(url)
        assert resp.status_code == 302
        assert 'complete' in resp.url

    def test_post_marks_order_as_paid(self, api_client, ec_order):
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.post(url, VALID_CARD_DATA)
        ec_order.refresh_from_db()
        assert ec_order.payment_status == 'paid'

    def test_post_closes_order(self, api_client, ec_order):
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        api_client.post(url, VALID_CARD_DATA)
        ec_order.refresh_from_db()
        assert ec_order.status == Order.STATUS_CLOSED

    def test_post_redirects_to_confirmation(self, api_client, ec_order):
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.post(url, VALID_CARD_DATA)
        assert resp.status_code == 302
        assert 'complete' in resp.url

    def test_post_validates_card_fields(self, api_client, ec_order):
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.post(url, {
            'card_number': '',
            'card_expiry': '',
            'card_cvv': '',
            'card_name': '',
        })
        # Should re-render the form (200) with error messages
        assert resp.status_code == 200
        ec_order.refresh_from_db()
        assert ec_order.payment_status == 'pending'


# ------------------------------------------------------------------
# ECOrderConfirmationView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestECOrderConfirmationView:
    def test_get_shows_order_details(self, api_client, paid_order):
        url = reverse('booking:shop_order_complete', kwargs={'order_id': paid_order.id})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.context['order'].id == paid_order.id

    def test_get_redirects_unpaid_order(self, api_client, ec_order):
        url = reverse('booking:shop_order_complete', kwargs={'order_id': ec_order.id})
        resp = api_client.get(url)
        assert resp.status_code == 302

    def test_context_includes_items(self, api_client, paid_order):
        url = reverse('booking:shop_order_complete', kwargs={'order_id': paid_order.id})
        resp = api_client.get(url)
        assert len(resp.context['items']) == 1
        assert resp.context['total'] == paid_order.items.first().qty * paid_order.items.first().unit_price


# ------------------------------------------------------------------
# ShopCheckoutView redirect to payment
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestShopCheckoutRedirect:
    def test_post_redirects_to_confirm(self, api_client, ec_product):
        """checkout POST → 確認画面へリダイレクト"""
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
        resp = api_client.post(url, {
            'customer_name': 'テスト太郎',
            'customer_email': 'test@example.com',
        })
        assert resp.status_code == 302
        assert 'confirm' in resp.url

    def test_confirm_post_creates_order(self, api_client, ec_product):
        """確認画面 POST → 注文作成 → 決済ページへリダイレクト"""
        session = api_client.session
        session['ec_cart'] = {
            str(ec_product.id): {
                'name': ec_product.name,
                'price': ec_product.price,
                'qty': 1,
            }
        }
        session['ec_customer'] = {
            'customer_name': 'テスト太郎',
            'customer_email': 'test@example.com',
            'customer_phone': '',
            'customer_address': '',
        }
        session.save()

        url = reverse('booking:shop_confirm')
        resp = api_client.post(url)
        assert resp.status_code == 302
        assert 'payment' in resp.url

        order = Order.objects.filter(channel='ec').last()
        assert order is not None
        assert order.customer_name == 'テスト太郎'


# ------------------------------------------------------------------
# seed_ec_goods management command
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestSeedECGoods:
    def test_creates_products(self, store):
        from django.core.management import call_command
        call_command('seed_ec_goods')
        count = Product.objects.filter(store=store, sku__startswith='EC-').count()
        assert count == 20

    def test_idempotent(self, store):
        from django.core.management import call_command
        call_command('seed_ec_goods')
        call_command('seed_ec_goods')
        count = Product.objects.filter(store=store, sku__startswith='EC-').count()
        assert count == 20

    def test_reset_flag(self, store):
        from django.core.management import call_command
        call_command('seed_ec_goods')
        call_command('seed_ec_goods', reset=True)
        count = Product.objects.filter(store=store, sku__startswith='EC-').count()
        assert count == 20
