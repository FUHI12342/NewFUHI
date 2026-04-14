"""EC注文管理ダッシュボード テスト"""
import json
import pytest
from django.test import Client
from booking.models import Order, OrderItem, Product, Category, Store


@pytest.fixture
def ec_order(db, store):
    """EC注文を作成"""
    return Order.objects.create(
        store=store,
        status=Order.STATUS_OPEN,
        channel='ec',
        table_label='EC: テスト太郎',
        customer_name='テスト太郎',
        customer_email='taro@example.com',
        customer_phone='090-1234-5678',
        customer_address='東京都新宿区1-1-1',
        shipping_status='pending',
    )


@pytest.fixture
def ec_order_with_items(ec_order, product):
    """商品付きEC注文"""
    OrderItem.objects.create(
        order=ec_order,
        product=product,
        qty=2,
        unit_price=product.price,
    )
    return ec_order


@pytest.mark.django_db
class TestECDashboardView:
    def test_dashboard_returns_200(self, admin_client):
        resp = admin_client.get('/admin/ec/orders/')
        assert resp.status_code == 200

    def test_dashboard_requires_auth(self):
        client = Client()
        resp = client.get('/admin/ec/orders/')
        assert resp.status_code in (302, 403)

    def test_dashboard_context_has_counts(self, admin_client, ec_order):
        resp = admin_client.get('/admin/ec/orders/')
        assert resp.status_code == 200
        assert resp.context['pending_count'] >= 1
        assert resp.context['total_count'] >= 1


@pytest.mark.django_db
class TestECOrderAPI:
    def test_list_ec_orders(self, admin_client, ec_order_with_items):
        resp = admin_client.get('/api/ec/orders/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data['orders']) >= 1
        order_data = data['orders'][0]
        assert order_data['customer_name'] == 'テスト太郎'
        assert order_data['customer_email'] == 'taro@example.com'
        assert order_data['customer_address'] == '東京都新宿区1-1-1'
        assert len(order_data['items']) >= 1

    def test_filter_by_shipping_status(self, admin_client, ec_order):
        resp = admin_client.get('/api/ec/orders/?shipping=pending')
        data = json.loads(resp.content)
        assert len(data['orders']) >= 1

        resp = admin_client.get('/api/ec/orders/?shipping=shipped')
        data = json.loads(resp.content)
        for order in data['orders']:
            assert order['shipping_status'] == 'shipped'

    def test_filter_by_date(self, admin_client, ec_order):
        from django.utils import timezone
        # ローカルタイムゾーン（Asia/Tokyo）で今日の日付を取得
        # created_at__date はローカルタイムゾーンに変換して比較するため
        today = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
        resp = admin_client.get(f'/api/ec/orders/?date_from={today}&date_to={today}')
        data = json.loads(resp.content)
        assert len(data['orders']) >= 1

    def test_unauthenticated_returns_401(self):
        client = Client()
        resp = client.get('/api/ec/orders/')
        assert resp.status_code == 401

    def test_non_ec_orders_excluded(self, admin_client, order):
        """POS注文はEC APIに含まれない"""
        resp = admin_client.get('/api/ec/orders/')
        data = json.loads(resp.content)
        order_ids = [o['id'] for o in data['orders']]
        assert order.id not in order_ids


@pytest.mark.django_db
class TestECOrderShippingAPI:
    def test_mark_shipped(self, admin_client, ec_order):
        resp = admin_client.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            json.dumps({'shipping_status': 'shipped'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['shipping_status'] == 'shipped'
        assert data['shipped_at'] is not None

        ec_order.refresh_from_db()
        assert ec_order.shipping_status == 'shipped'
        assert ec_order.shipped_at is not None

    def test_mark_delivered(self, admin_client, ec_order):
        ec_order.shipping_status = 'shipped'
        ec_order.save(update_fields=['shipping_status'])

        resp = admin_client.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            json.dumps({'shipping_status': 'delivered'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['shipping_status'] == 'delivered'

    def test_update_tracking_number(self, admin_client, ec_order):
        resp = admin_client.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            json.dumps({'tracking_number': '1234-5678-9012'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        ec_order.refresh_from_db()
        assert ec_order.tracking_number == '1234-5678-9012'

    def test_update_shipping_note(self, admin_client, ec_order):
        resp = admin_client.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            json.dumps({'shipping_note': '割れ物注意'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        ec_order.refresh_from_db()
        assert ec_order.shipping_note == '割れ物注意'

    def test_invalid_status_returns_400(self, admin_client, ec_order):
        resp = admin_client.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            json.dumps({'shipping_status': 'invalid'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_not_found_returns_404(self, admin_client):
        resp = admin_client.put(
            '/api/ec/orders/99999/shipping/',
            json.dumps({'shipping_status': 'shipped'}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_unauthenticated_returns_401(self):
        client = Client()
        resp = client.put(
            '/api/ec/orders/1/shipping/',
            json.dumps({'shipping_status': 'shipped'}),
            content_type='application/json',
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestShopCheckoutDataSaving:
    """ShopCheckoutView が顧客データを正しく保存するか検証"""

    def test_checkout_saves_customer_fields(self, db, store, product):
        """チェックアウト→確認画面→注文確定で顧客データが正しく保存される"""
        product.is_ec_visible = True
        product.save(update_fields=['is_ec_visible'])

        client = Client()
        session = client.session
        session['ec_cart'] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 1,
            }
        }
        session.save()

        # Step 1: checkout POST → 確認画面へリダイレクト
        resp = client.post('/shop/checkout/', {
            'customer_name': '山田花子',
            'customer_email': 'hanako@example.com',
            'customer_phone': '080-9999-0000',
            'customer_address': '大阪府大阪市1-2-3',
        })
        assert resp.status_code == 302
        assert 'confirm' in resp.url

        # Step 2: confirm POST → 注文作成 → 決済ページへリダイレクト
        resp = client.post('/shop/confirm/')
        assert resp.status_code == 302

        order = Order.objects.filter(channel='ec').order_by('-id').first()
        assert order is not None
        assert order.customer_name == '山田花子'
        assert order.customer_email == 'hanako@example.com'
        assert order.customer_phone == '080-9999-0000'
        assert order.customer_address == '大阪府大阪市1-2-3'
        assert order.shipping_status == 'pending'
        assert order.table_label == 'EC: 山田花子'
