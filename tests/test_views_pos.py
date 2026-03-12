"""POSテスト"""
import json
import pytest
from django.test import Client
from booking.models import Order, OrderItem, POSTransaction
from booking.admin_site import GROUPS, HIDDEN_SLUGS


@pytest.mark.django_db
class TestPOSView:
    def test_pos_returns_200(self, admin_client):
        resp = admin_client.get('/admin/pos/')
        assert resp.status_code == 200

    def test_kitchen_returns_200(self, admin_client):
        resp = admin_client.get('/admin/pos/kitchen/')
        assert resp.status_code == 200

    def test_pos_requires_auth(self):
        client = Client()
        resp = client.get('/admin/pos/')
        assert resp.status_code in (302, 403)


@pytest.mark.django_db
class TestPOSOrderAPI:
    def test_list_orders(self, admin_client, order):
        resp = admin_client.get('/api/pos/orders/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert len(data) >= 1

    def test_create_order(self, admin_client, store):
        resp = admin_client.post(
            '/api/pos/orders/',
            json.dumps({'table_label': 'A1'}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert data['table_label'] == 'A1'

    def test_add_item(self, admin_client, order, product):
        resp = admin_client.post(
            '/api/pos/order-items/',
            json.dumps({'order_id': order.id, 'product_id': product.id, 'qty': 2}),
            content_type='application/json',
        )
        assert resp.status_code == 201

    def test_update_item_qty(self, admin_client, order_item):
        resp = admin_client.put(
            f'/api/pos/order-items/{order_item.id}/',
            json.dumps({'qty': 5}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        order_item.refresh_from_db()
        assert order_item.qty == 5

    def test_delete_item(self, admin_client, order_item):
        resp = admin_client.delete(f'/api/pos/order-items/{order_item.id}/')
        assert resp.status_code == 204


@pytest.mark.django_db
class TestPOSCheckout:
    def test_checkout_success(self, admin_client, order, order_item):
        resp = admin_client.post(
            '/api/pos/checkout/',
            json.dumps({'order_id': order.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'receipt_number' in data
        assert data['total'] > 0
        order.refresh_from_db()
        assert order.status == Order.STATUS_CLOSED

    def test_checkout_with_cash(self, admin_client, order, order_item):
        resp = admin_client.post(
            '/api/pos/checkout/',
            json.dumps({'order_id': order.id, 'cash_received': 5000}),
            content_type='application/json',
        )
        data = json.loads(resp.content)
        assert data['change'] is not None

    def test_checkout_creates_transaction(self, admin_client, order, order_item):
        admin_client.post(
            '/api/pos/checkout/',
            json.dumps({'order_id': order.id}),
            content_type='application/json',
        )
        assert POSTransaction.objects.filter(order=order).exists()

    def test_checkout_with_payment_method(self, admin_client, order, order_item, payment_method):
        resp = admin_client.post(
            '/api/pos/checkout/',
            json.dumps({'order_id': order.id, 'payment_method_id': payment_method.id}),
            content_type='application/json',
        )
        data = json.loads(resp.content)
        assert data['total'] > 0

    def test_checkout_updates_stock(self, admin_client, order, order_item, product):
        initial_stock = product.stock
        admin_client.post(
            '/api/pos/checkout/',
            json.dumps({'order_id': order.id}),
            content_type='application/json',
        )
        product.refresh_from_db()
        assert product.stock < initial_stock


@pytest.mark.django_db
class TestKitchenDisplay:
    def test_kitchen_shows_orders(self, admin_client, order, order_item):
        resp = admin_client.get('/admin/pos/kitchen/')
        assert resp.status_code == 200

    def test_update_item_status(self, admin_client, order_item):
        resp = admin_client.put(
            f'/api/pos/order-item/{order_item.id}/status/',
            json.dumps({'status': 'PREPARING'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        order_item.refresh_from_db()
        assert order_item.status == 'PREPARING'

    def test_invalid_status(self, admin_client, order_item):
        resp = admin_client.put(
            f'/api/pos/order-item/{order_item.id}/status/',
            json.dumps({'status': 'INVALID'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_kitchen_html_fragment_returns_html(self, admin_client, order, order_item):
        """HTMX auto-refresh用エンドポイントがHTMLを返すことを確認"""
        resp = admin_client.get('/api/pos/kitchen-orders/?status=OPEN')
        assert resp.status_code == 200
        assert resp['Content-Type'].startswith('text/html')

    def test_kitchen_html_fragment_contains_order(self, admin_client, order, order_item):
        """HTMLフラグメントに注文カードが含まれることを確認"""
        resp = admin_client.get('/api/pos/kitchen-orders/?status=OPEN')
        content = resp.content.decode()
        assert 'order-card' in content
        assert order_item.product.name in content

    def test_kitchen_html_fragment_empty(self, admin_client, store):
        """注文がない場合のHTMLフラグメント"""
        resp = admin_client.get('/api/pos/kitchen-orders/?status=OPEN')
        assert resp.status_code == 200
        content = resp.content.decode()
        assert '注文はありません' in content


class TestIoTMenuHidden:
    """IoTメニューがサイドバーに表示されないことを確認"""

    def test_iot_group_is_hidden(self):
        """GROUPS内のiotグループにhidden: Trueが設定されていること"""
        iot_group = next(g for g in GROUPS if g['slug'] == 'iot')
        assert iot_group.get('hidden') is True

    def test_iot_in_hidden_slugs(self):
        """HIDDEN_SLUGSにiotが含まれていること"""
        assert 'iot' in HIDDEN_SLUGS
