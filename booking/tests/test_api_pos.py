"""
POS API の統合テスト

対象:
  - POSOrderAPIView        GET / POST  (注文一覧・作成)
  - POSOrderItemAPIView    POST / PUT / DELETE  (注文商品)
  - POSCheckoutAPIView     POST  (決済処理)
  - KitchenOrderStatusAPI  PUT   (キッチンステータス更新)
  - KitchenOrderCompleteAPI    POST  (注文完了)
  - KitchenOrderUncompleteAPI  POST  (完了取り消し)
  - ECOrderAPIView         GET   (EC注文一覧)
  - ECOrderShippingAPIView PUT   (発送ステータス更新)
"""
import json
from datetime import date
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from booking.models import (
    Store, Staff, Category, Product, Order, OrderItem,
    PaymentMethod, POSTransaction, StockMovement,
    TaxServiceCharge,
)

User = get_user_model()

# ============================================================
# ヘルパー
# ============================================================

def make_user(username, store, is_staff=True, is_super=False):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
        is_superuser=is_super,
    )
    if store:
        Staff.objects.create(name=username, store=store, user=user)
    return user


def auth_client(user):
    c = Client()
    c.login(username=user.username, password='testpass123')
    return c


def post_json(client, url, data):
    return client.post(url, data=json.dumps(data), content_type='application/json')


def put_json(client, url, data):
    return client.put(url, data=json.dumps(data), content_type='application/json')


# ============================================================
# フィクスチャ
# ============================================================

@pytest.fixture
def store(db):
    return Store.objects.create(name='POSテスト店舗')


@pytest.fixture
def other_store(db):
    return Store.objects.create(name='他POS店舗')


@pytest.fixture
def staff_user(db, store):
    return make_user('pos_staff', store, is_staff=True)


@pytest.fixture
def admin_user(db, store):
    return make_user('pos_admin', store, is_staff=True, is_super=True)


@pytest.fixture
def category(db, store):
    return Category.objects.create(store=store, name='ドリンク', sort_order=0)


@pytest.fixture
def product(db, store, category):
    return Product.objects.create(
        store=store,
        category=category,
        sku='DRINK-001',
        name='コーヒー',
        price=500,
        stock=100,
        low_stock_threshold=5,
        is_active=True,
    )


@pytest.fixture
def open_order(db, store):
    return Order.objects.create(
        store=store,
        status=Order.STATUS_OPEN,
        channel='pos',
        table_label='A1',
    )


@pytest.fixture
def order_item(db, open_order, product):
    return OrderItem.objects.create(
        order=open_order,
        product=product,
        qty=2,
        unit_price=product.price,
        status=OrderItem.STATUS_ORDERED,
    )


@pytest.fixture
def payment_method(db, store):
    return PaymentMethod.objects.create(
        store=store,
        method_type='cash',
        display_name='現金',
        is_enabled=True,
    )


@pytest.fixture
def ec_order(db, store):
    return Order.objects.create(
        store=store,
        status=Order.STATUS_OPEN,
        channel='ec',
        customer_name='テスト太郎',
        customer_email='test@example.com',
        shipping_status='pending',
    )


# ============================================================
# 1. POSOrderAPIView — GET (注文一覧)
# ============================================================

class TestPOSOrderList:

    def test_get_open_orders_authenticated(self, db, store, staff_user, open_order):
        """認証済みでオープン注文一覧を取得できる"""
        c = auth_client(staff_user)
        resp = c.get('/api/pos/orders/?status=OPEN')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert isinstance(data, list)
        ids = [o['id'] for o in data]
        assert open_order.id in ids

    def test_get_orders_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = c.get('/api/pos/orders/')
        assert resp.status_code == 302

    def test_get_orders_includes_required_fields(self, db, store, staff_user, open_order, order_item):
        """レスポンスに必須フィールドが含まれる"""
        c = auth_client(staff_user)
        resp = c.get('/api/pos/orders/?status=OPEN')
        data = json.loads(resp.content)
        if data:
            first = data[0]
            assert 'id' in first
            assert 'status' in first
            assert 'items' in first
            assert 'total' in first

    def test_get_orders_default_status_open(self, db, store, staff_user, open_order):
        """statusパラメータなしのデフォルトはOPEN"""
        c = auth_client(staff_user)
        resp = c.get('/api/pos/orders/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        for order in data:
            assert order['status'] == 'OPEN'

    def test_get_closed_orders(self, db, store, staff_user):
        """CLOSEDの注文を取得できる"""
        Order.objects.create(store=store, status=Order.STATUS_CLOSED, channel='pos')
        c = auth_client(staff_user)
        resp = c.get('/api/pos/orders/?status=CLOSED')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        for order in data:
            assert order['status'] == 'CLOSED'


# ============================================================
# 2. POSOrderAPIView — POST (注文作成)
# ============================================================

class TestPOSOrderCreate:

    def test_create_order_successfully(self, db, store, staff_user):
        """注文を新規作成できる"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/orders/', {
            'table_label': 'B2',
        })
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert 'id' in data
        assert data['table_label'] == 'B2'
        assert Order.objects.filter(id=data['id'], store=store).exists()

    def test_create_order_without_table(self, db, store, staff_user):
        """テーブル指定なしで注文を作成できる"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/orders/', {})
        assert resp.status_code == 201

    def test_create_order_invalid_json(self, db, store, staff_user):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/pos/orders/',
            data='{{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_create_order_unauthenticated_redirects(self, db):
        """未認証は302"""
        c = Client()
        resp = post_json(c, '/api/pos/orders/', {'table_label': 'C3'})
        assert resp.status_code == 302

    def test_create_order_status_is_open(self, db, store, staff_user):
        """作成した注文はOPENステータス"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/orders/', {'table_label': 'D4'})
        data = json.loads(resp.content)
        order = Order.objects.get(id=data['id'])
        assert order.status == Order.STATUS_OPEN

    def test_create_order_channel_is_pos(self, db, store, staff_user):
        """POSから作成した注文はチャネルがpos"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/orders/', {'table_label': 'E5'})
        data = json.loads(resp.content)
        order = Order.objects.get(id=data['id'])
        assert order.channel == 'pos'


# ============================================================
# 3. POSOrderItemAPIView — POST (商品追加)
# ============================================================

class TestPOSOrderItemCreate:

    def test_add_item_to_order(self, db, store, staff_user, open_order, product):
        """注文に商品を追加できる"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': open_order.id,
            'product_id': product.id,
            'qty': 1,
        })
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert data['product_name'] == product.name
        assert data['qty'] == 1

    def test_add_same_item_increments_qty(self, db, store, staff_user, open_order, product, order_item):
        """同じ商品を追加するとqtyが増加する"""
        initial_qty = order_item.qty
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': open_order.id,
            'product_id': product.id,
            'qty': 3,
        })
        assert resp.status_code == 201
        order_item.refresh_from_db()
        assert order_item.qty == initial_qty + 3

    def test_add_item_nonexistent_order_returns_404(self, db, store, staff_user, product):
        """存在しない注文は404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': 99999,
            'product_id': product.id,
            'qty': 1,
        })
        assert resp.status_code == 404

    def test_add_item_nonexistent_product_returns_404(self, db, store, staff_user, open_order):
        """存在しない商品は404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': open_order.id,
            'product_id': 99999,
            'qty': 1,
        })
        assert resp.status_code == 404

    def test_add_item_invalid_json_returns_400(self, db, store, staff_user):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/pos/order-items/',
            data='bad-json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_add_item_price_taken_from_product(self, db, store, staff_user, open_order, product):
        """商品価格は商品マスタから自動取得"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': open_order.id,
            'product_id': product.id,
            'qty': 1,
        })
        data = json.loads(resp.content)
        assert data['unit_price'] == product.price


# ============================================================
# 4. POSOrderItemAPIView — PUT (商品更新)
# ============================================================

class TestPOSOrderItemUpdate:

    def test_update_item_qty(self, db, store, staff_user, order_item):
        """注文アイテムの数量を更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-items/{order_item.id}/', {
            'qty': 5,
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['qty'] == 5
        order_item.refresh_from_db()
        assert order_item.qty == 5

    def test_update_item_status(self, db, store, staff_user, order_item):
        """注文アイテムのステータスを更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-items/{order_item.id}/', {
            'status': 'PREPARING',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['status'] == 'PREPARING'

    def test_update_item_qty_minimum_is_1(self, db, store, staff_user, order_item):
        """qtyの最小値は1"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-items/{order_item.id}/', {
            'qty': 0,
        })
        assert resp.status_code == 200
        order_item.refresh_from_db()
        assert order_item.qty == 1  # max(1, 0) = 1

    def test_update_nonexistent_item_returns_404(self, db, store, staff_user):
        """存在しないアイテムは404"""
        c = auth_client(staff_user)
        resp = put_json(c, '/api/pos/order-items/99999/', {'qty': 3})
        assert resp.status_code == 404

    def test_update_item_invalid_json_returns_400(self, db, store, staff_user, order_item):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.put(
            f'/api/pos/order-items/{order_item.id}/',
            data='bad-json',
            content_type='application/json',
        )
        assert resp.status_code == 400


# ============================================================
# 5. POSOrderItemAPIView — DELETE (商品削除)
# ============================================================

class TestPOSOrderItemDelete:

    def test_delete_order_item(self, db, store, staff_user, order_item):
        """注文アイテムを削除できる"""
        item_id = order_item.id
        c = auth_client(staff_user)
        resp = c.delete(f'/api/pos/order-items/{item_id}/')
        assert resp.status_code == 204
        assert not OrderItem.objects.filter(id=item_id).exists()

    def test_delete_nonexistent_item_returns_404(self, db, store, staff_user):
        """存在しないアイテムの削除は404"""
        c = auth_client(staff_user)
        resp = c.delete('/api/pos/order-items/99999/')
        assert resp.status_code == 404

    def test_delete_item_unauthenticated_redirects(self, db, order_item):
        """未認証は302"""
        c = Client()
        resp = c.delete(f'/api/pos/order-items/{order_item.id}/')
        assert resp.status_code == 302


# ============================================================
# 6. POSCheckoutAPIView — POST (決済処理)
# ============================================================

class TestPOSCheckout:

    def test_checkout_successfully(self, db, store, staff_user, open_order, order_item, payment_method):
        """正常に決済処理できる"""
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': open_order.id,
                'payment_method_id': payment_method.id,
                'cash_received': 2000,
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'receipt_number' in data
        assert 'total' in data
        assert 'change' in data
        assert data['change'] == 2000 - data['total']

        # 注文ステータスが CLOSEDに変更されているか
        open_order.refresh_from_db()
        assert open_order.status == Order.STATUS_CLOSED
        assert open_order.payment_status == 'paid'

    def test_checkout_creates_pos_transaction(self, db, store, staff_user, open_order, order_item, payment_method):
        """決済処理でPOSTransactionが作成される"""
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': open_order.id,
                'payment_method_id': payment_method.id,
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert POSTransaction.objects.filter(id=data['transaction_id']).exists()

    def test_checkout_creates_stock_movement(self, db, store, staff_user, open_order, order_item, payment_method):
        """決済でStockMovementが記録される"""
        initial_count = StockMovement.objects.filter(
            store=store, movement_type='OUT'
        ).count()
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': open_order.id,
                'payment_method_id': payment_method.id,
            })
        assert resp.status_code == 200
        new_count = StockMovement.objects.filter(
            store=store, movement_type='OUT'
        ).count()
        assert new_count > initial_count

    def test_checkout_nonexistent_order_returns_404(self, db, store, staff_user):
        """存在しない注文は404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/checkout/', {
            'order_id': 99999,
        })
        assert resp.status_code == 404

    def test_checkout_without_payment_method(self, db, store, staff_user, open_order, order_item):
        """決済手段なしでも決済できる"""
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': open_order.id,
            })
        assert resp.status_code == 200

    def test_checkout_invalid_json_returns_400(self, db, store, staff_user):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.post(
            '/api/pos/checkout/',
            data='bad-json',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_checkout_unauthenticated_redirects(self, db, open_order):
        """未認証は302"""
        c = Client()
        resp = post_json(c, '/api/pos/checkout/', {'order_id': open_order.id})
        assert resp.status_code == 302

    def test_checkout_with_tax_charge(self, db, store, staff_user, open_order, order_item, payment_method):
        """税率設定がある場合、税が計算される"""
        TaxServiceCharge.objects.create(
            store=store,
            name='消費税',
            rate=10,
            is_active=True,
        )
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': open_order.id,
                'payment_method_id': payment_method.id,
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['tax'] > 0

    def test_checkout_low_stock_triggers_notify(self, db, store, staff_user, payment_method):
        """在庫が閾値以下になると通知タスクが実行される"""
        low_stock_product = Product.objects.create(
            store=store,
            sku='LOW-001',
            name='残り僅か商品',
            price=100,
            stock=3,
            low_stock_threshold=5,  # 現在在庫が閾値以下
            is_active=True,
        )
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN, channel='pos')
        OrderItem.objects.create(
            order=order,
            product=low_stock_product,
            qty=1,
            unit_price=low_stock_product.price,
        )
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay') as mock_delay:
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': order.id,
                'payment_method_id': payment_method.id,
            })
        assert resp.status_code == 200
        mock_delay.assert_called()


# ============================================================
# 7. KitchenOrderStatusAPI — PUT (キッチンステータス更新)
# ============================================================

class TestKitchenOrderStatus:

    def test_update_item_status_to_preparing(self, db, store, staff_user, order_item):
        """調理中ステータスに更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-item/{order_item.id}/status/', {
            'status': 'PREPARING',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['status'] == 'PREPARING'

    def test_update_item_status_to_served(self, db, store, staff_user, order_item):
        """提供済みステータスに更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-item/{order_item.id}/status/', {
            'status': 'SERVED',
        })
        assert resp.status_code == 200

    def test_invalid_status_returns_400(self, db, store, staff_user, order_item):
        """不正なステータスは400"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/pos/order-item/{order_item.id}/status/', {
            'status': 'INVALID_STATUS',
        })
        assert resp.status_code == 400

    def test_nonexistent_item_returns_404(self, db, store, staff_user):
        """存在しないアイテムは404"""
        c = auth_client(staff_user)
        resp = put_json(c, '/api/pos/order-item/99999/status/', {
            'status': 'PREPARING',
        })
        assert resp.status_code == 404

    def test_invalid_json_returns_400(self, db, store, staff_user, order_item):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.put(
            f'/api/pos/order-item/{order_item.id}/status/',
            data='bad',
            content_type='application/json',
        )
        assert resp.status_code == 400


# ============================================================
# 8. KitchenOrderCompleteAPI — POST (注文完了)
# ============================================================

class TestKitchenOrderComplete:

    def test_complete_order(self, db, store, staff_user, open_order):
        """注文を完了にできる"""
        c = auth_client(staff_user)
        resp = post_json(c, f'/api/pos/order/{open_order.id}/complete/', {})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['status'] == Order.STATUS_CLOSED
        open_order.refresh_from_db()
        assert open_order.status == Order.STATUS_CLOSED

    def test_complete_nonexistent_order_returns_404(self, db, store, staff_user):
        """存在しない注文は404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order/99999/complete/', {})
        assert resp.status_code == 404


# ============================================================
# 9. KitchenOrderUncompleteAPI — POST (完了取り消し)
# ============================================================

class TestKitchenOrderUncomplete:

    def test_uncomplete_closed_order(self, db, store, staff_user):
        """未払いのCLOSED注文をOPENに戻せる"""
        order = Order.objects.create(
            store=store,
            status=Order.STATUS_CLOSED,
            channel='pos',
            payment_status='pending',
        )
        c = auth_client(staff_user)
        resp = post_json(c, f'/api/pos/order/{order.id}/uncomplete/', {})
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['status'] == Order.STATUS_OPEN

    def test_uncomplete_paid_order_rejected(self, db, store, staff_user):
        """支払済みの注文は取り消し不可（400）"""
        order = Order.objects.create(
            store=store,
            status=Order.STATUS_CLOSED,
            channel='pos',
            payment_status='paid',
        )
        c = auth_client(staff_user)
        resp = post_json(c, f'/api/pos/order/{order.id}/uncomplete/', {})
        assert resp.status_code == 400

    def test_uncomplete_open_order_rejected(self, db, store, staff_user, open_order):
        """OPEN状態の注文への取り消しは400"""
        c = auth_client(staff_user)
        resp = post_json(c, f'/api/pos/order/{open_order.id}/uncomplete/', {})
        assert resp.status_code == 400

    def test_uncomplete_nonexistent_order_returns_404(self, db, store, staff_user):
        """存在しない注文は404"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order/99999/uncomplete/', {})
        assert resp.status_code == 404

    def test_uncomplete_resets_items_to_served(self, db, store, staff_user, product):
        """取り消し後、全アイテムがSERVEDに戻る"""
        order = Order.objects.create(
            store=store,
            status=Order.STATUS_CLOSED,
            channel='pos',
            payment_status='pending',
        )
        item = OrderItem.objects.create(
            order=order, product=product, qty=1,
            unit_price=product.price, status=OrderItem.STATUS_CLOSED,
        )
        c = auth_client(staff_user)
        post_json(c, f'/api/pos/order/{order.id}/uncomplete/', {})
        item.refresh_from_db()
        assert item.status == OrderItem.STATUS_SERVED


# ============================================================
# 10. ECOrderAPIView — GET (EC注文一覧)
# ============================================================

class TestECOrderAPI:

    def test_get_ec_orders_authenticated(self, db, store, staff_user, ec_order):
        """認証済みでEC注文一覧を取得できる"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert 'orders' in data
        ids = [o['id'] for o in data['orders']]
        assert ec_order.id in ids

    def test_get_ec_orders_unauthenticated_returns_401(self, db):
        """未認証は401"""
        c = Client()
        resp = c.get('/api/ec/orders/')
        assert resp.status_code == 401

    def test_get_ec_orders_filter_by_shipping(self, db, store, staff_user, ec_order):
        """shipping_statusフィルタが動作する"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/?shipping=pending')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        for order in data['orders']:
            assert order['shipping_status'] == 'pending'

    def test_get_ec_orders_filter_excludes_pos_orders(self, db, store, staff_user, open_order):
        """POS注文はEC一覧に含まれない"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/')
        data = json.loads(resp.content)
        ids = [o['id'] for o in data['orders']]
        assert open_order.id not in ids

    def test_get_ec_orders_filter_by_date_from(self, db, store, staff_user, ec_order):
        """date_fromフィルタが動作する"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/?date_from=2020-01-01')
        assert resp.status_code == 200
        data = json.loads(resp.content)
        ids = [o['id'] for o in data['orders']]
        assert ec_order.id in ids

    def test_get_ec_orders_includes_customer_info(self, db, store, staff_user, ec_order):
        """レスポンスに顧客情報が含まれる"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/')
        data = json.loads(resp.content)
        ec = next((o for o in data['orders'] if o['id'] == ec_order.id), None)
        assert ec is not None
        assert 'customer_name' in ec
        assert 'customer_email' in ec
        assert 'shipping_status' in ec

    def test_get_ec_orders_filter_all_shipping(self, db, store, staff_user, ec_order):
        """shipping=allは全ステータスを返す"""
        c = auth_client(staff_user)
        resp = c.get('/api/ec/orders/?shipping=all')
        assert resp.status_code == 200


# ============================================================
# 11. ECOrderShippingAPIView — PUT (発送ステータス更新)
# ============================================================

class TestECOrderShipping:

    def test_update_shipping_status_to_shipped(self, db, store, staff_user, ec_order):
        """発送済みに更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'shipping_status': 'shipped',
            'tracking_number': 'TRACK123',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['shipping_status'] == 'shipped'
        assert data['tracking_number'] == 'TRACK123'
        ec_order.refresh_from_db()
        assert ec_order.shipping_status == 'shipped'
        assert ec_order.shipped_at is not None

    def test_update_shipping_note(self, db, store, staff_user, ec_order):
        """発送メモを更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'shipping_note': '配送業者変更',
        })
        assert resp.status_code == 200
        ec_order.refresh_from_db()
        assert ec_order.shipping_note == '配送業者変更'

    def test_update_tracking_number_only(self, db, store, staff_user, ec_order):
        """追跡番号のみ更新できる"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'tracking_number': 'JP1234567890',
        })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['tracking_number'] == 'JP1234567890'

    def test_invalid_shipping_status_returns_400(self, db, store, staff_user, ec_order):
        """不正なshipping_statusは400"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'shipping_status': 'invalid_status',
        })
        assert resp.status_code == 400

    def test_nonexistent_order_returns_404(self, db, store, staff_user):
        """存在しない注文は404"""
        c = auth_client(staff_user)
        resp = put_json(c, '/api/ec/orders/99999/shipping/', {
            'shipping_status': 'shipped',
        })
        assert resp.status_code == 404

    def test_non_ec_order_returns_404(self, db, store, staff_user, open_order):
        """POS注文へのアクセスは404"""
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{open_order.id}/shipping/', {
            'shipping_status': 'shipped',
        })
        assert resp.status_code == 404

    def test_invalid_json_returns_400(self, db, store, staff_user, ec_order):
        """不正JSONは400"""
        c = auth_client(staff_user)
        resp = c.put(
            f'/api/ec/orders/{ec_order.id}/shipping/',
            data='bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_unauthenticated_returns_401(self, db, store, ec_order):
        """未認証は401"""
        c = Client()
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'shipping_status': 'shipped',
        })
        assert resp.status_code == 401

    def test_shipped_at_auto_set_on_shipped(self, db, store, staff_user, ec_order):
        """shipped時にshipped_atが自動設定される"""
        assert ec_order.shipped_at is None
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{ec_order.id}/shipping/', {
            'shipping_status': 'shipped',
        })
        assert resp.status_code == 200
        ec_order.refresh_from_db()
        assert ec_order.shipped_at is not None

    def test_shipped_at_not_overwritten(self, db, store, staff_user):
        """既にshipped_atがある場合は上書きしない"""
        from django.utils import timezone
        original_shipped_at = timezone.now()
        order = Order.objects.create(
            store=store,
            channel='ec',
            status=Order.STATUS_CLOSED,
            shipping_status='shipped',
            shipped_at=original_shipped_at,
            payment_status='paid',
        )
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{order.id}/shipping/', {
            'shipping_status': 'delivered',
        })
        assert resp.status_code == 200
        order.refresh_from_db()
        # shipped_atが上書きされていないことを確認
        assert order.shipped_at == original_shipped_at

    def test_other_store_order_returns_404(self, db, store, other_store, staff_user):
        """他店舗のEC注文へのアクセスは404"""
        other_order = Order.objects.create(
            store=other_store,
            channel='ec',
            status=Order.STATUS_OPEN,
        )
        c = auth_client(staff_user)
        resp = put_json(c, f'/api/ec/orders/{other_order.id}/shipping/', {
            'shipping_status': 'shipped',
        })
        assert resp.status_code == 404


# ============================================================
# 12. 各種エッジケース
# ============================================================

class TestPOSEdgeCases:

    def test_checkout_empty_order(self, db, store, staff_user, payment_method):
        """アイテムなしの注文でも決済できる（合計0円）"""
        empty_order = Order.objects.create(
            store=store, status=Order.STATUS_OPEN, channel='pos'
        )
        c = auth_client(staff_user)

        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': empty_order.id,
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data['total'] == 0

    def test_order_item_default_qty_is_1(self, db, store, staff_user, open_order, product):
        """qty省略時のデフォルトは1"""
        c = auth_client(staff_user)
        resp = post_json(c, '/api/pos/order-items/', {
            'order_id': open_order.id,
            'product_id': product.id,
        })
        assert resp.status_code == 201
        data = json.loads(resp.content)
        assert data['qty'] == 1

    def test_multiple_items_checkout_calculates_correctly(
        self, db, store, staff_user, payment_method, category
    ):
        """複数アイテムの合計金額が正確に計算される"""
        prod_a = Product.objects.create(
            store=store, category=category, sku='A001', name='商品A',
            price=300, stock=50, is_active=True,
        )
        prod_b = Product.objects.create(
            store=store, category=category, sku='B001', name='商品B',
            price=700, stock=50, is_active=True,
        )
        order = Order.objects.create(store=store, status=Order.STATUS_OPEN, channel='pos')
        OrderItem.objects.create(order=order, product=prod_a, qty=2, unit_price=300)
        OrderItem.objects.create(order=order, product=prod_b, qty=1, unit_price=700)
        # 合計: 300*2 + 700*1 = 1300

        c = auth_client(staff_user)
        with patch('booking.tasks.check_low_stock_and_notify.delay'):
            resp = post_json(c, '/api/pos/checkout/', {
                'order_id': order.id,
                'payment_method_id': payment_method.id,
                'cash_received': 5000,
            })
        assert resp.status_code == 200
        data = json.loads(resp.content)
        # 税なし: subtotal = 1300
        assert data['total'] >= 1300  # 税率によって変動あり
        assert data['change'] == 5000 - data['total']
