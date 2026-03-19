"""
Phase 3: 決済・予約ビューのテスト

対象:
  - coiney_webhook (views.py:1545-1573)
  - process_payment (views.py:1459-1541)
  - EmailBookingView (views.py:1087-1137)
  - EmailVerifyView (views.py:1139-1257)
  - CancelReservationView (views.py:1260-1301)
  - OrderCreateAPIView (views.py:1677-1812)
"""
import hashlib
import hmac
import json
import uuid

import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory
from django.utils import timezone

from booking.models import (
    Store, Staff, Schedule, Category, Product, Order, OrderItem,
    StockMovement,
)

User = get_user_model()

pytestmark = pytest.mark.django_db


# ==============================
# Fixtures
# ==============================

@pytest.fixture
def store_p(db):
    return Store.objects.create(
        name="決済テスト店舗", address="東京", business_hours="10-22",
        nearest_station="渋谷",
    )


@pytest.fixture
def staff_member(store_p):
    user = User.objects.create_user(
        username="payment_staff", password="pass123", email="pstaff@test.com",
        is_staff=True,
    )
    return Staff.objects.create(
        name="決済スタッフ", store=store_p, user=user, line_id="staff_line_id",
    )


@pytest.fixture
def schedule_confirmed(staff_member):
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=2),
        staff=staff_member,
        is_temporary=True,
        customer_name="テスト顧客",
        price=5000,
    )


@pytest.fixture
def schedule_email(staff_member):
    now = timezone.now()
    return Schedule.objects.create(
        start=now + timedelta(hours=1),
        end=now + timedelta(hours=2),
        staff=staff_member,
        is_temporary=True,
        customer_name="メール顧客",
        customer_email="customer@example.com",
        booking_channel='email',
        price=5000,
    )


@pytest.fixture
def admin_pay(store_p):
    user = User.objects.create_superuser(
        username="pay_admin", password="pass123", email="padmin@test.com",
    )
    Staff.objects.create(name="管理者", store=store_p, user=user)
    client = Client()
    client.login(username="pay_admin", password="pass123")
    return client


@pytest.fixture
def staff_client(staff_member):
    client = Client()
    client.login(username="payment_staff", password="pass123")
    return client


@pytest.fixture
def anon_client():
    return Client()


@pytest.fixture
def product_stock(store_p):
    cat = Category.objects.create(store=store_p, name="Cat", sort_order=0)
    return Product.objects.create(
        store=store_p, category=cat, sku="STOCK-01",
        name="在庫商品", price=500, stock=10, low_stock_threshold=5, is_active=True,
    )


def _set_session(client, data):
    """Helper to set session data on a test client."""
    # Need to make a request first so session exists
    client.get('/booking/email/')  # any URL that doesn't 500
    session = client.session
    for k, v in data.items():
        session[k] = v
    session.save()


# ==============================
# coiney_webhook tests
# ==============================

class TestCoineyWebhook:
    """Tests for coiney_webhook view function."""

    def test_get_returns_405(self, anon_client):
        """GET method → 405."""
        resp = anon_client.get('/coiney_webhook/test-order-id/')
        assert resp.status_code == 405

    def test_missing_webhook_secret(self, anon_client, settings):
        """No COINEY_WEBHOOK_SECRET → 500."""
        settings.COINEY_WEBHOOK_SECRET = None
        resp = anon_client.post(
            '/coiney_webhook/test-order-id/',
            data=json.dumps({"type": "payment.succeeded"}),
            content_type='application/json',
        )
        assert resp.status_code == 500

    def test_invalid_signature(self, anon_client, settings):
        """Invalid HMAC signature → 403."""
        settings.COINEY_WEBHOOK_SECRET = 'test-secret'
        resp = anon_client.post(
            '/coiney_webhook/test-order-id/',
            data=json.dumps({"type": "payment.succeeded"}),
            content_type='application/json',
            HTTP_X_COINEY_SIGNATURE='invalid-signature',
        )
        assert resp.status_code == 403

    @patch('booking.views_booking.PayingSuccessView')
    def test_valid_signature_delegates(self, mock_view_cls, anon_client, settings):
        """Valid signature → delegates to PayingSuccessView.post."""
        settings.COINEY_WEBHOOK_SECRET = 'test-secret'
        body = json.dumps({"type": "payment.succeeded"}).encode()
        expected_sig = hmac.new(
            b'test-secret', body, hashlib.sha256
        ).hexdigest()

        mock_view = MagicMock()
        from django.http import JsonResponse
        mock_view.post.return_value = JsonResponse({"status": "ok"})
        mock_view_cls.return_value = mock_view

        resp = anon_client.post(
            '/coiney_webhook/test-order-id/',
            data=body,
            content_type='application/json',
            HTTP_X_COINEY_SIGNATURE=expected_sig,
        )
        mock_view.post.assert_called_once()


# ==============================
# process_payment tests
# ==============================

class TestProcessPayment:
    """Tests for process_payment function."""

    def test_non_success_type(self):
        """Non-success payment type → still returns success (no-op)."""
        from booking.views import process_payment
        factory = RequestFactory()
        request = factory.post('/fake/')
        result = process_payment({"type": "payment.failed"}, request, "nonexistent")
        assert result.status_code == 200
        data = json.loads(result.content)
        assert data['status'] == 'success'

    @patch('booking.views_booking.LineBotApi')
    @patch('booking.views_booking._build_access_lines', return_value='')
    def test_success_confirms_schedule(
        self, mock_access, mock_linebot_cls, schedule_confirmed, settings
    ):
        """payment.succeeded → schedule.is_temporary becomes False."""
        from booking.views import process_payment
        settings.LINE_ACCESS_TOKEN = 'test-token'
        mock_linebot_cls.return_value = MagicMock()

        factory = RequestFactory()
        request = factory.post('/fake/')
        result = process_payment(
            {"type": "payment.succeeded"}, request,
            str(schedule_confirmed.reservation_number),
        )
        assert result.status_code == 200
        schedule_confirmed.refresh_from_db()
        assert schedule_confirmed.is_temporary is False

    @patch('booking.views_booking.LineBotApi')
    @patch('booking.views_booking._build_access_lines', return_value='')
    def test_success_generates_qr(
        self, mock_access, mock_linebot_cls, schedule_confirmed, settings
    ):
        """payment.succeeded → QR code generated."""
        from booking.views import process_payment
        settings.LINE_ACCESS_TOKEN = 'test-token'
        mock_linebot_cls.return_value = MagicMock()

        factory = RequestFactory()
        request = factory.post('/fake/')
        with patch('booking.services.qr_service.generate_checkin_qr') as mock_qr:
            from io import BytesIO
            from django.core.files.uploadedfile import SimpleUploadedFile
            mock_qr.return_value = SimpleUploadedFile('test.png', b'\x89PNG', content_type='image/png')
            process_payment(
                {"type": "payment.succeeded"}, request,
                str(schedule_confirmed.reservation_number),
            )
            mock_qr.assert_called_once()

    def test_schedule_not_found(self):
        """Schedule not found → 404."""
        from booking.views import process_payment
        factory = RequestFactory()
        request = factory.post('/fake/')
        result = process_payment(
            {"type": "payment.succeeded"}, request, "nonexistent-uuid"
        )
        assert result.status_code == 404

    @patch('booking.views_booking.LineBotApi')
    @patch('booking.views_booking._build_access_lines', return_value='')
    @patch('booking.views_booking.send_mail')
    def test_email_booking_sends_confirmation(
        self, mock_mail, mock_access, mock_linebot_cls, schedule_email, settings
    ):
        """Email booking → sends confirmation email."""
        from booking.views import process_payment
        settings.LINE_ACCESS_TOKEN = 'test-token'
        settings.DEFAULT_FROM_EMAIL = 'noreply@test.com'
        mock_linebot_cls.return_value = MagicMock()

        factory = RequestFactory()
        request = factory.post('/fake/')
        with patch('booking.services.qr_service.generate_checkin_qr') as mock_qr:
            from django.core.files.uploadedfile import SimpleUploadedFile
            mock_qr.return_value = SimpleUploadedFile('test.png', b'\x89PNG', content_type='image/png')
            process_payment(
                {"type": "payment.succeeded"}, request,
                str(schedule_email.reservation_number),
            )
        mock_mail.assert_called_once()
        call_args = mock_mail.call_args
        # Check recipient_list contains the customer email
        if call_args.kwargs:
            assert 'customer@example.com' in call_args.kwargs.get('recipient_list', [])
        else:
            assert 'customer@example.com' in call_args[0][3]


# ==============================
# EmailBookingView tests
# ==============================

class TestEmailBookingView:
    """Tests for EmailBookingView."""
    URL = '/booking/email/'

    def test_get_no_session(self, anon_client):
        """GET without temporary_booking → redirect."""
        resp = anon_client.get(self.URL)
        assert resp.status_code == 302

    def test_get_with_session(self, anon_client, staff_member):
        """GET with session data → 200."""
        _set_session(anon_client, {
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            }
        })
        resp = anon_client.get(self.URL)
        assert resp.status_code == 200

    def test_post_no_session(self, anon_client):
        """POST without session → redirect."""
        resp = anon_client.post(self.URL, {'customer_name': 'test', 'customer_email': 'a@b.com'})
        assert resp.status_code == 302

    @patch('booking.views_booking.send_mail')
    def test_post_valid_sends_otp(self, mock_mail, anon_client, staff_member):
        """Valid POST → sends OTP email."""
        _set_session(anon_client, {
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            }
        })
        resp = anon_client.post(self.URL, {
            'customer_name': 'テスト太郎',
            'customer_email': 'test@example.com',
        })
        assert resp.status_code == 302  # redirect to email_verify
        mock_mail.assert_called_once()

    def test_post_invalid_form(self, anon_client, staff_member):
        """Invalid form → re-renders form."""
        _set_session(anon_client, {
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            }
        })
        resp = anon_client.post(self.URL, {
            'customer_name': '',
            'customer_email': 'not-an-email',
        })
        assert resp.status_code == 200  # re-render

    @patch('booking.views_booking.send_mail', side_effect=Exception('SMTP error'))
    def test_post_mail_failure(self, mock_mail, anon_client, staff_member):
        """Mail send failure → re-renders form with error."""
        _set_session(anon_client, {
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            }
        })
        resp = anon_client.post(self.URL, {
            'customer_name': 'テスト',
            'customer_email': 'test@example.com',
        })
        assert resp.status_code == 200  # re-render with error


# ==============================
# EmailVerifyView tests
# ==============================

class TestEmailVerifyView:
    """Tests for EmailVerifyView."""
    URL = '/booking/email/verify/'

    def test_get_no_session(self, anon_client):
        """GET without session → redirect."""
        resp = anon_client.get(self.URL)
        assert resp.status_code == 302

    def test_post_no_session(self, anon_client):
        """POST without session → redirect."""
        resp = anon_client.post(self.URL, {'otp': '123456'})
        assert resp.status_code == 302

    def test_post_wrong_otp(self, anon_client, staff_member):
        """Wrong OTP → re-renders form with error."""
        otp = '123456'
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        _set_session(anon_client, {
            'email_booking': {
                'customer_name': 'テスト',
                'customer_email': 'test@example.com',
                'otp_hash': otp_hash,
                'otp_expires': (timezone.now() + timedelta(minutes=10)).isoformat(),
            },
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            },
        })
        resp = anon_client.post(self.URL, {'otp': '999999'})
        assert resp.status_code == 200  # re-render with error

    def test_post_expired_otp(self, anon_client, staff_member):
        """Expired OTP → redirect to email_booking."""
        otp = '123456'
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        _set_session(anon_client, {
            'email_booking': {
                'customer_name': 'テスト',
                'customer_email': 'test@example.com',
                'otp_hash': otp_hash,
                'otp_expires': (timezone.now() - timedelta(minutes=1)).isoformat(),
            },
            'temporary_booking': {
                'reservation_number': str(uuid.uuid4()),
                'staff_id': staff_member.id,
                'start': timezone.now().isoformat(),
                'end': (timezone.now() + timedelta(hours=1)).isoformat(),
                'price': 5000,
            },
        })
        resp = anon_client.post(self.URL, {'otp': otp})
        assert resp.status_code == 302  # redirect back

    @patch('booking.views_booking.requests.post')
    @patch('booking.views_booking.send_mail')
    def test_post_valid_otp(self, mock_mail, mock_requests, anon_client, staff_member, settings):
        """Valid OTP → creates schedule, gets payment URL."""
        settings.PAYMENT_API_URL = 'https://api.coiney.io/test'
        settings.PAYMENT_API_KEY = 'test-key'
        settings.WEBHOOK_URL_BASE = 'https://example.com/webhook/'
        settings.CANCEL_URL = 'https://example.com/cancel'

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {'links': {'paymentUrl': 'https://pay.example.com/test'}}
        mock_requests.return_value = mock_resp

        otp = '123456'
        otp_hash = hashlib.sha256(otp.encode('utf-8')).hexdigest()
        reservation_number = str(uuid.uuid4())
        # Use naive datetime (the view calls make_aware)
        from datetime import datetime as dt
        now_naive = dt.now()

        _set_session(anon_client, {
            'email_booking': {
                'customer_name': 'テスト',
                'customer_email': 'test@example.com',
                'otp_hash': otp_hash,
                'otp_expires': (timezone.now() + timedelta(minutes=10)).isoformat(),
            },
            'temporary_booking': {
                'reservation_number': reservation_number,
                'staff_id': staff_member.id,
                'start': now_naive.isoformat(),
                'end': (now_naive + timedelta(hours=1)).isoformat(),
                'price': 5000,
            },
        })
        resp = anon_client.post(self.URL, {'otp': otp})
        assert resp.status_code == 200  # renders email_payment_sent.html

        # Schedule was created
        schedule = Schedule.objects.get(reservation_number=reservation_number)
        assert schedule.customer_name == 'テスト'
        assert schedule.booking_channel == 'email'
        assert schedule.email_verified is True
        assert schedule.payment_url == 'https://pay.example.com/test'

        # Payment URL email was sent
        assert mock_mail.call_count >= 1


# ==============================
# CancelReservationView tests
# ==============================

class TestCancelReservationView:
    """Tests for CancelReservationView."""

    def _url(self, schedule_id):
        return f'/cancel_reservation/{schedule_id}/'

    def test_unauthenticated(self, anon_client, schedule_confirmed):
        resp = anon_client.post(self._url(schedule_confirmed.id))
        assert resp.status_code == 302  # redirect to login

    @patch('booking.views_booking.LineBotApi')
    def test_staff_can_cancel(self, mock_linebot_cls, staff_client, schedule_confirmed):
        """Staff user can cancel any schedule."""
        mock_linebot_cls.return_value = MagicMock()
        resp = staff_client.post(self._url(schedule_confirmed.id))
        assert resp.status_code == 200
        schedule_confirmed.refresh_from_db()
        assert schedule_confirmed.is_cancelled is True

    @patch('booking.views_booking.LineBotApi')
    def test_admin_can_cancel(self, mock_linebot_cls, admin_pay, schedule_confirmed):
        """Admin can cancel any schedule."""
        mock_linebot_cls.return_value = MagicMock()
        resp = admin_pay.post(self._url(schedule_confirmed.id))
        assert resp.status_code == 200
        schedule_confirmed.refresh_from_db()
        assert schedule_confirmed.is_cancelled is True

    def test_not_found(self, staff_client):
        resp = staff_client.post(self._url(99999))
        assert resp.status_code == 404

    @patch('booking.views_booking.LineBotApi')
    def test_line_notification_failure_graceful(
        self, mock_linebot_cls, staff_client, schedule_confirmed
    ):
        """LINE notification failure doesn't break cancellation."""
        mock_linebot = MagicMock()
        mock_linebot.push_message.side_effect = Exception('LINE error')
        mock_linebot_cls.return_value = mock_linebot
        resp = staff_client.post(self._url(schedule_confirmed.id))
        assert resp.status_code == 200
        schedule_confirmed.refresh_from_db()
        assert schedule_confirmed.is_cancelled is True


# ==============================
# OrderCreateAPIView tests
# ==============================

class TestOrderCreateAPI:
    """Tests for OrderCreateAPIView."""
    URL = '/api/orders/create/'

    def _reset_rate_limit(self):
        from booking.views import OrderCreateAPIView
        OrderCreateAPIView._rate_limit_cache.clear()

    def test_missing_store_id(self, anon_client):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({"items": [{"product_id": 1, "qty": 1}]}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_empty_items(self, anon_client, store_p):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({"store_id": store_p.id, "items": []}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_items_over_50(self, anon_client, store_p):
        self._reset_rate_limit()
        items = [{"product_id": i, "qty": 1} for i in range(51)]
        resp = anon_client.post(
            self.URL,
            json.dumps({"store_id": store_p.id, "items": items}),
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_store_not_found(self, anon_client, db):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({"store_id": 99999, "items": [{"product_id": 1, "qty": 1}]}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_product_not_found(self, anon_client, store_p):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({"store_id": store_p.id, "items": [{"product_id": 99999, "qty": 1}]}),
            content_type='application/json',
        )
        assert resp.status_code == 404

    def test_insufficient_stock(self, anon_client, store_p, product_stock):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({
                "store_id": store_p.id,
                "items": [{"product_id": product_stock.id, "qty": 999}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 409

    def test_successful_order(self, anon_client, store_p, product_stock):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({
                "store_id": store_p.id,
                "items": [{"product_id": product_stock.id, "qty": 2}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        data = resp.json()
        assert 'order_id' in data

        # Verify stock deducted
        product_stock.refresh_from_db()
        assert product_stock.stock == 8

        # Verify order items created
        order = Order.objects.get(id=data['order_id'])
        assert order.items.count() == 1
        assert StockMovement.objects.filter(note__contains=f"order#{order.id}").exists()

    def test_invalid_qty_skipped(self, anon_client, store_p, product_stock):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({
                "store_id": store_p.id,
                "items": [
                    {"product_id": product_stock.id, "qty": 1},
                    {"product_id": product_stock.id, "qty": "invalid"},
                ],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201

    def test_duplicate_products_aggregated(self, anon_client, store_p, product_stock):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({
                "store_id": store_p.id,
                "items": [
                    {"product_id": product_stock.id, "qty": 1},
                    {"product_id": product_stock.id, "qty": 2},
                ],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 201
        product_stock.refresh_from_db()
        assert product_stock.stock == 7  # 10 - 3

    def test_zero_qty_rejected(self, anon_client, store_p, product_stock):
        self._reset_rate_limit()
        resp = anon_client.post(
            self.URL,
            json.dumps({
                "store_id": store_p.id,
                "items": [{"product_id": product_stock.id, "qty": 0}],
            }),
            content_type='application/json',
        )
        assert resp.status_code == 400
