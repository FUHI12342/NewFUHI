"""
tests/test_api_table_order.py
Table order APIs: TableCartAddAPI, TableCartUpdateAPI, TableCartRemoveAPI,
TableOrderCreateAPI, TableOrderStatusAPI.
"""
import json
import pytest
from django.urls import reverse
from booking.models import Product, Order, OrderItem


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


# ------------------------------------------------------------------
# TableCartAddAPI
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableCartAddAPI:
    def test_add_product_to_cart(self, api_client, table_seat, product):
        url = reverse('booking_api:table_cart_add', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 2}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ok'
        assert data['cart_count'] == 2

    def test_add_product_accumulates_qty(self, api_client, table_seat, product):
        url = reverse('booking_api:table_cart_add', kwargs={'table_id': table_seat.pk})
        api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 1}),
            content_type='application/json',
        )
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 3}),
            content_type='application/json',
        )
        assert resp.json()['cart_count'] == 4

    def test_product_not_found_returns_404(self, api_client, table_seat):
        url = reverse('booking_api:table_cart_add', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': 99999, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_insufficient_stock_returns_400(self, api_client, table_seat, product):
        product.stock = 0
        product.save()
        url = reverse('booking_api:table_cart_add', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_table_returns_404(self, api_client, product):
        import uuid
        url = reverse('booking_api:table_cart_add', kwargs={'table_id': uuid.uuid4()})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 1}),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# TableCartUpdateAPI
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableCartUpdateAPI:
    def _seed_cart(self, api_client, table_seat, product):
        cart_key = f'table_cart_{table_seat.pk}'
        session = api_client.session
        session[cart_key] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 3,
            }
        }
        session.save()

    def test_update_qty(self, api_client, table_seat, product):
        self._seed_cart(api_client, table_seat, product)
        url = reverse('booking_api:table_cart_update', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 5}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 5

    def test_qty_zero_removes_item(self, api_client, table_seat, product):
        self._seed_cart(api_client, table_seat, product)
        url = reverse('booking_api:table_cart_update', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id, 'qty': 0}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 0

    def test_update_nonexistent_returns_404(self, api_client, table_seat):
        url = reverse('booking_api:table_cart_update', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': 99999, 'qty': 2}),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# TableCartRemoveAPI
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableCartRemoveAPI:
    def test_remove_product(self, api_client, table_seat, product):
        cart_key = f'table_cart_{table_seat.pk}'
        session = api_client.session
        session[cart_key] = {
            str(product.id): {
                'name': product.name,
                'price': product.price,
                'qty': 2,
            }
        }
        session.save()

        url = reverse('booking_api:table_cart_remove', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': product.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 0

    def test_remove_nonexistent_is_noop(self, api_client, table_seat):
        url = reverse('booking_api:table_cart_remove', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'product_id': 99999}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['cart_count'] == 0


# ------------------------------------------------------------------
# TableOrderCreateAPI
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableOrderCreateAPI:
    def test_create_order(self, api_client, table_seat, product):
        url = reverse('booking_api:table_order_create', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'items': [{'product_id': product.id, 'qty': 2}]}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert 'order_id' in data

        order = Order.objects.get(pk=data['order_id'])
        assert order.table_seat == table_seat
        assert order.items.count() == 1
        assert order.items.first().qty == 2

        product.refresh_from_db()
        assert product.stock == 98  # 100 - 2

    def test_insufficient_stock_returns_409(self, api_client, table_seat, product):
        product.stock = 1
        product.save()
        url = reverse('booking_api:table_order_create', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'items': [{'product_id': product.id, 'qty': 5}]}),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_empty_items_returns_400(self, api_client, table_seat):
        url = reverse('booking_api:table_order_create', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'items': []}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_product_not_found_returns_404(self, api_client, table_seat):
        url = reverse('booking_api:table_order_create', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'items': [{'product_id': 99999, 'qty': 1}]}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_multiple_items_order(self, api_client, table_seat, product, store, category):
        product2 = Product.objects.create(
            store=store,
            category=category,
            sku='TEST-002',
            name='テスト商品2',
            price=800,
            stock=50,
            is_active=True,
        )
        url = reverse('booking_api:table_order_create', kwargs={'table_id': table_seat.pk})
        resp = api_client.post(
            url,
            data=json.dumps({'items': [
                {'product_id': product.id, 'qty': 1},
                {'product_id': product2.id, 'qty': 3},
            ]}),
            content_type='application/json',
        )
        assert resp.status_code == 201
        order = Order.objects.get(pk=resp.json()['order_id'])
        assert order.items.count() == 2


# ------------------------------------------------------------------
# TableOrderStatusAPI
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestTableOrderStatusAPI:
    def test_get_order_status(self, api_client, table_seat, product):
        order = Order.objects.create(
            store=table_seat.store,
            table_seat=table_seat,
            table_label=table_seat.label,
            status=Order.STATUS_OPEN,
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            qty=1,
            unit_price=product.price,
            status=OrderItem.STATUS_ORDERED,
        )
        orders_key = f'table_orders_{table_seat.pk}'
        session = api_client.session
        session[orders_key] = [order.id]
        session.save()

        url = reverse('booking_api:table_order_status', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert 'orders' in data
        assert len(data['orders']) == 1
        assert data['orders'][0]['order_id'] == order.id
        assert data['orders'][0]['items'][0]['status'] == 'ORDERED'

    def test_empty_orders(self, api_client, table_seat):
        url = reverse('booking_api:table_order_status', kwargs={'table_id': table_seat.pk})
        resp = api_client.get(url)
        assert resp.status_code == 200
        assert resp.json()['orders'] == []
