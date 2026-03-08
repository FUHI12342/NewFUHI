"""
tests/test_api_order.py
Order APIs: OrderCreateAPIView, OrderStatusAPIView,
StaffMarkServedAPIView, OrderItemStatusUpdateAPIView.
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
# OrderCreateAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderCreateAPIView:
    def test_creates_order(self, api_client, store, product):
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'items': [{'product_id': product.id, 'qty': 2}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert 'order_id' in data

        order = Order.objects.get(pk=data['order_id'])
        assert order.store == store
        assert order.items.count() == 1
        assert order.items.first().qty == 2

        product.refresh_from_db()
        assert product.stock == 98  # 100 - 2

    def test_insufficient_stock_returns_409(self, api_client, store, product):
        product.stock = 1
        product.save()
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'items': [{'product_id': product.id, 'qty': 10}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_missing_items_returns_400(self, api_client, store):
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'items': [],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_missing_store_id_returns_400(self, api_client):
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({'items': [{'product_id': 1, 'qty': 1}]}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_items_returns_400(self, api_client, store):
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'items': [{'product_id': None, 'qty': 0}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_product_not_found_returns_404(self, api_client, store):
        url = reverse('booking_api:order_create_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'items': [{'product_id': 99999, 'qty': 1}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# OrderStatusAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderStatusAPIView:
    def test_returns_order_with_items(self, api_client, order, order_item):
        url = reverse('booking_api:order_status_api')
        resp = api_client.get(url, {'order_id': order.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data['order_id'] == order.id
        assert data['status'] == Order.STATUS_OPEN
        assert len(data['items']) == 1
        assert data['items'][0]['qty'] == order_item.qty

    def test_missing_order_id_returns_400(self, api_client):
        url = reverse('booking_api:order_status_api')
        resp = api_client.get(url)
        assert resp.status_code == 400

    def test_nonexistent_order_returns_404(self, api_client):
        url = reverse('booking_api:order_status_api')
        resp = api_client.get(url, {'order_id': 99999})
        assert resp.status_code == 404


# ------------------------------------------------------------------
# StaffMarkServedAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestStaffMarkServedAPIView:
    def test_marks_item_as_served(self, authenticated_client, order_item):
        url = reverse('booking_api:staff_mark_served_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({'order_item_id': order_item.id}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['status'] == OrderItem.STATUS_SERVED

        order_item.refresh_from_db()
        assert order_item.status == OrderItem.STATUS_SERVED

    def test_requires_login(self, api_client, order_item):
        url = reverse('booking_api:staff_mark_served_api')
        resp = api_client.post(
            url,
            data=json.dumps({'order_item_id': order_item.id}),
            content_type='application/json',
        )
        # LoginRequiredMixin redirects unauthenticated requests
        assert resp.status_code == 302 or resp.status_code == 403

    def test_missing_item_id_returns_400(self, authenticated_client):
        url = reverse('booking_api:staff_mark_served_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------
# OrderItemStatusUpdateAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestOrderItemStatusUpdateAPIView:
    def test_ordered_to_preparing(self, authenticated_client, order_item):
        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({'status': 'PREPARING'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['status'] == 'PREPARING'
        order_item.refresh_from_db()
        assert order_item.status == OrderItem.STATUS_PREPARING

    def test_preparing_to_served(self, authenticated_client, order_item):
        order_item.status = OrderItem.STATUS_PREPARING
        order_item.save()

        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({'status': 'SERVED'}),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['status'] == 'SERVED'

    def test_skip_transition_returns_409(self, authenticated_client, order_item):
        """ORDERED -> SERVED directly should be rejected."""
        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({'status': 'SERVED'}),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_already_served_returns_409(self, authenticated_client, order_item):
        order_item.status = OrderItem.STATUS_SERVED
        order_item.save()

        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({'status': 'SERVED'}),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_missing_status_returns_400(self, authenticated_client, order_item):
        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_invalid_status_value_returns_400(self, authenticated_client, order_item):
        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = authenticated_client.post(
            url,
            data=json.dumps({'status': 'INVALID'}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_requires_login(self, api_client, order_item):
        url = reverse(
            'booking_api:order_item_status_update_api',
            kwargs={'item_id': order_item.id},
        )
        resp = api_client.post(
            url,
            data=json.dumps({'status': 'PREPARING'}),
            content_type='application/json',
        )
        assert resp.status_code == 302 or resp.status_code == 403
