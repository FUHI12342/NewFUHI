"""
tests/test_ec_coiney_payment.py
Coiney EC決済統合 + 管理画面メニューリネーム + 占い師一覧枠情報
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from django.test import Client
from django.urls import reverse

from booking.admin_site import GROUPS, SIDEBAR_CUSTOM_LINKS_BY_ROLE
from booking.models import (
    Category, Order, OrderItem, PaymentMethod, Product,
    Staff, StoreScheduleConfig,
)


@pytest.fixture(autouse=True)
def mock_line_settings(settings):
    settings.LINE_CHANNEL_ID = 'test-channel-id'
    settings.LINE_CHANNEL_SECRET = 'test-channel-secret'
    settings.LINE_REDIRECT_URL = 'http://testserver/callback'
    settings.LINE_ACCESS_TOKEN = 'test-access-token'
    settings.PAYMENT_API_URL = 'https://api.example.com/payge'
    settings.PAYMENT_API_KEY = 'test-api-key'
    settings.WEBHOOK_URL_BASE = 'https://example.com/booking/coiney_webhook/'


@pytest.fixture
def ec_product(db, store, category):
    return Product.objects.create(
        store=store,
        category=category,
        sku='EC-COINEY-001',
        name='Coineyテスト商品',
        price=2000,
        stock=10,
        is_active=True,
        is_ec_visible=True,
    )


@pytest.fixture
def ec_order(db, store, ec_product):
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
        qty=1,
        unit_price=ec_product.price,
    )
    return order


@pytest.fixture
def coiney_method(db, store):
    return PaymentMethod.objects.create(
        store=store,
        method_type='coiney',
        display_name='Coiney クレジットカード',
        is_enabled=True,
        api_key='test-coiney-key',
        api_endpoint='https://api.example.com/payge',
    )


# ------------------------------------------------------------------
# TestCoineyECPayment
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestCoineyECPayment:

    def test_get_with_coiney_redirects(self, api_client, ec_order, coiney_method):
        """Coiney 有効時、API成功で Coiney決済URLへリダイレクト"""
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'links': {'paymentUrl': 'https://payge.co/pay/test123'}
        }

        with patch('booking.views_ec_payment.requests.post', return_value=mock_response) as mock_post:
            url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
            resp = api_client.get(url)

        assert resp.status_code == 302
        assert 'payge.co' in resp.url
        mock_post.assert_called_once()

    def test_get_without_coiney_shows_mock_form(self, api_client, ec_order):
        """Coiney 未設定時はモック決済フォームを表示"""
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
        resp = api_client.get(url)

        assert resp.status_code == 200
        assert 'order' in resp.context

    def test_get_coiney_api_failure_falls_back_to_mock(
        self, api_client, ec_order, coiney_method
    ):
        """Coiney API失敗時はモック決済フォームにフォールバック"""
        session = api_client.session
        session['ec_pending_order_id'] = ec_order.id
        session.save()

        with patch('booking.views_ec_payment.requests.post', side_effect=Exception('API error')):
            url = reverse('booking:shop_payment', kwargs={'order_id': ec_order.id})
            resp = api_client.get(url)

        assert resp.status_code == 200
        assert 'order' in resp.context

    def test_coiney_webhook_ec_order(self, api_client, ec_order, settings):
        """EC注文のwebhook → order paid"""
        settings.COINEY_WEBHOOK_SECRET = 'test-secret'

        import hmac
        import hashlib
        body = json.dumps({'type': 'payment.succeeded'}).encode()
        sig = hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()

        url = reverse('coiney_webhook', kwargs={
            'orderId': f'ec_order_{ec_order.id}'
        })
        resp = api_client.post(
            url, body, content_type='application/json',
            HTTP_X_COINEY_SIGNATURE=sig,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'success'

        ec_order.refresh_from_db()
        assert ec_order.payment_status == 'paid'
        assert ec_order.status == Order.STATUS_CLOSED

    def test_coiney_webhook_ignores_non_success(self, api_client, ec_order, settings):
        """type != payment.succeeded → ignored"""
        settings.COINEY_WEBHOOK_SECRET = 'test-secret'

        import hmac
        import hashlib
        body = json.dumps({'type': 'payment.failed'}).encode()
        sig = hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()

        url = reverse('coiney_webhook', kwargs={
            'orderId': f'ec_order_{ec_order.id}'
        })
        resp = api_client.post(
            url, body, content_type='application/json',
            HTTP_X_COINEY_SIGNATURE=sig,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['status'] == 'ignored'

        ec_order.refresh_from_db()
        assert ec_order.payment_status == 'pending'


# ------------------------------------------------------------------
# TestAdminMenuRename
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminMenuRename:

    def test_staff_manage_group_renamed(self):
        """GROUPS の staff_manage の name が「従業員管理」"""
        group = next(g for g in GROUPS if g['slug'] == 'staff_manage')
        assert str(group['name']) == '従業員管理'

    def test_cast_group_removed(self):
        """cast グループは削除済み"""
        slugs = [g['slug'] for g in GROUPS]
        assert 'cast' not in slugs

    def test_manager_links_exactly_two(self):
        """manager の従業員管理メニューは2項目のみ（従業員一覧 + 勤怠実績）"""
        links = SIDEBAR_CUSTOM_LINKS_BY_ROLE['staff_manage']['manager']
        assert len(links) == 2
        link_names = [str(link['name']) for link in links]
        assert '従業員一覧' in link_names
        assert '勤怠実績' in link_names


# ------------------------------------------------------------------
# TestFortuneTellerSlotInfo
# ------------------------------------------------------------------

@pytest.mark.django_db
class TestFortuneTellerSlotInfo:

    def test_slot_duration_in_queryset(self, db, store, store_schedule_config):
        """AllFortuneTellerList の queryset で schedule_config が取得可能"""
        from booking.views import AllFortuneTellerList
        from django.contrib.auth.models import User

        user = User.objects.create_user(username='ft-test', password='pass')
        Staff.objects.create(
            store=store,
            user=user,
            name='テスト占い師',
            staff_type='fortune_teller',
            price=5000,
        )

        view = AllFortuneTellerList()
        view.kwargs = {}
        view.request = None
        qs = view.get_queryset()
        staff = qs.first()

        assert staff is not None
        assert staff.store.schedule_config.slot_duration == 60
