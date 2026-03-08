"""
tests/test_api_stock.py
InboundApplyAPIView tests: stock inbound operations.
"""
import json
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from booking.models import Store, Staff, Product, StockMovement

User = get_user_model()


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'


# ------------------------------------------------------------------
# InboundApplyAPIView
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestInboundApplyAPIView:
    def test_successful_inbound_increases_stock(self, authenticated_client, store, product):
        url = reverse('booking_api:inbound_apply_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': 10,
                'note': '仕入れテスト',
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['stock'] == 110  # 100 + 10

        product.refresh_from_db()
        assert product.stock == 110

        # Verify StockMovement was created
        sm = StockMovement.objects.filter(product=product, movement_type=StockMovement.TYPE_IN).first()
        assert sm is not None
        assert sm.qty == 10

    def test_missing_fields_returns_400(self, authenticated_client, store):
        url = reverse('booking_api:inbound_apply_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({'store_id': store.id}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_product_not_found_returns_404(self, authenticated_client, store):
        url = reverse('booking_api:inbound_apply_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': 'NONEXISTENT-SKU',
                'qty': 5,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_requires_login(self, api_client, store, product):
        url = reverse('booking_api:inbound_apply_api')
        resp = api_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': 5,
            }),
            content_type='application/json',
        )
        # LoginRequiredMixin redirects unauthenticated requests
        assert resp.status_code == 302 or resp.status_code == 403

    def test_store_permission_check(self, db, store, product):
        """Staff from a different store should be denied."""
        other_store = Store.objects.create(
            name="別店舗",
            address="大阪市",
            business_hours="10:00-20:00",
            nearest_station="梅田駅",
        )
        other_user = User.objects.create_user(
            username="otherstaff",
            password="otherpass123",
            email="other@example.com",
        )
        Staff.objects.create(name="別スタッフ", store=other_store, user=other_user)

        from django.test import Client
        client = Client()
        client.login(username="otherstaff", password="otherpass123")

        url = reverse('booking_api:inbound_apply_api')
        resp = client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': 5,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 403

    def test_qty_zero_returns_400(self, authenticated_client, store, product):
        url = reverse('booking_api:inbound_apply_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': 0,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_negative_qty_returns_400(self, authenticated_client, store, product):
        url = reverse('booking_api:inbound_apply_api')
        resp = authenticated_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': -5,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_admin_can_inbound_any_store(self, admin_client, store, product):
        url = reverse('booking_api:inbound_apply_api')
        resp = admin_client.post(
            url,
            data=json.dumps({
                'store_id': store.id,
                'sku': product.sku,
                'qty': 20,
            }),
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['stock'] == 120  # 100 + 20
