"""Tests for the unified Coiney payment service."""
import datetime
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from booking.services.payment_service import CoineyPaymentError, create_payment_link


# ---------------------------------------------------------------------------
# 共通テストデータ
# ---------------------------------------------------------------------------

BASE_KWARGS = dict(
    amount=5000,
    subject="カット",
    description="ヘアカット施術",
    remarks="予約番号 RES-001",
    reservation_number="RES-001",
    webhook_token="tok123",
    webhook_url_base="https://example.com/webhook/",
    cancel_url="https://example.com/cancel/",
)


def _make_response(status_code: int, body: dict) -> MagicMock:
    """requests.Response のモックを生成する。"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = body
    mock_resp.text = json.dumps(body)
    return mock_resp


# ---------------------------------------------------------------------------
# テストクラス
# ---------------------------------------------------------------------------


class TestCreatePaymentLink:
    """create_payment_link() のテストスイート。"""

    # ------------------------------------------------------------------
    # 成功系
    # ------------------------------------------------------------------

    @patch("booking.services.payment_service.requests.post")
    def test_successful_payment_link_creation(self, mock_post, settings):
        """201レスポンスでpaymentUrlが返る場合、URLを返す。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        expected_url = "https://coiney.io/pay/abc123"
        mock_post.return_value = _make_response(
            201, {"links": {"paymentUrl": expected_url}}
        )

        result = create_payment_link(**BASE_KWARGS)

        assert result == expected_url

    @patch("booking.services.payment_service.requests.post")
    def test_custom_api_url_and_key_used(self, mock_post, settings):
        """api_url/api_key 引数がsettingsより優先される。"""
        settings.PAYMENT_API_URL = "https://wrong.example.com"
        settings.PAYMENT_API_KEY = "wrong-key"

        custom_url = "https://custom.api.example.com/v1/payments"
        custom_key = "custom-key-xyz"

        mock_post.return_value = _make_response(
            201, {"links": {"paymentUrl": "https://coiney.io/pay/xyz"}}
        )

        create_payment_link(
            **BASE_KWARGS,
            api_url=custom_url,
            api_key=custom_key,
        )

        call_args = mock_post.call_args
        assert call_args[0][0] == custom_url
        assert f"Bearer {custom_key}" in call_args[1]["headers"]["Authorization"]

    @patch("booking.services.payment_service.requests.post")
    def test_webhook_url_constructed_correctly(self, mock_post, settings):
        """Webhook URLが <base><reservation_number>/?token=<token> 形式で組み立てられる。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.return_value = _make_response(
            201, {"links": {"paymentUrl": "https://coiney.io/pay/x"}}
        )

        create_payment_link(**BASE_KWARGS)

        call_args = mock_post.call_args
        sent_data = json.loads(call_args[1]["data"])
        expected_webhook = "https://example.com/webhook/RES-001/?token=tok123"
        assert sent_data["webhookUrl"] == expected_webhook

    @patch("booking.services.payment_service.requests.post")
    def test_expired_on_included_when_provided(self, mock_post, settings):
        """expired_on が指定されると、リクエストボディに expiredOn が含まれる。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.return_value = _make_response(
            201, {"links": {"paymentUrl": "https://coiney.io/pay/x"}}
        )

        create_payment_link(**BASE_KWARGS, expired_on="2026-12-31")

        call_args = mock_post.call_args
        sent_data = json.loads(call_args[1]["data"])
        assert sent_data["expiredOn"] == "2026-12-31"

    @patch("booking.services.payment_service.requests.post")
    def test_timeout_set_on_request(self, mock_post, settings):
        """requests.post が timeout=30 で呼ばれる。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.return_value = _make_response(
            201, {"links": {"paymentUrl": "https://coiney.io/pay/x"}}
        )

        create_payment_link(**BASE_KWARGS)

        call_args = mock_post.call_args
        assert call_args[1]["timeout"] == 30

    # ------------------------------------------------------------------
    # API未設定系
    # ------------------------------------------------------------------

    def test_returns_none_when_api_not_configured(self, settings):
        """PAYMENT_API_URL 未設定時は None を返す。"""
        settings.PAYMENT_API_URL = ""
        settings.PAYMENT_API_KEY = "test-api-key"

        result = create_payment_link(**BASE_KWARGS)

        assert result is None

    def test_returns_none_when_api_key_not_configured(self, settings):
        """PAYMENT_API_KEY 未設定時は None を返す。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = ""

        result = create_payment_link(**BASE_KWARGS)

        assert result is None

    # ------------------------------------------------------------------
    # 失敗系
    # ------------------------------------------------------------------

    @patch("booking.services.payment_service.requests.post")
    def test_raises_error_on_request_exception(self, mock_post, settings):
        """requests.RequestException 発生時は CoineyPaymentError を送出する。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.side_effect = requests.RequestException("connection refused")

        with pytest.raises(CoineyPaymentError):
            create_payment_link(**BASE_KWARGS)

    @patch("booking.services.payment_service.requests.post")
    def test_returns_none_on_non_201_status(self, mock_post, settings):
        """400 レスポンス時は例外を送出せず None を返す。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.return_value = _make_response(400, {"error": "bad request"})

        result = create_payment_link(**BASE_KWARGS)

        assert result is None

    @patch("booking.services.payment_service.requests.post")
    def test_returns_none_when_no_payment_url_in_response(self, mock_post, settings):
        """201 レスポンスでも paymentUrl が欠けている場合は None を返す。"""
        settings.PAYMENT_API_URL = "https://api.coiney.io/payments"
        settings.PAYMENT_API_KEY = "test-api-key"

        mock_post.return_value = _make_response(201, {"links": {}})

        result = create_payment_link(**BASE_KWARGS)

        assert result is None


# ---------------------------------------------------------------------------
# Webhook・返金フロー用ヘルパー
# ---------------------------------------------------------------------------

def _create_confirmed_schedule(price=5000, is_temporary=False, is_cancelled=False,
                                cancel_token='CANCEL01', booking_channel='line',
                                customer_email=None):
    """テスト用の確定済みスケジュールを作成する。"""
    from booking.models import Store, Staff, Schedule
    from django.contrib.auth.models import User

    store = Store.objects.create(name='テスト店舗')
    user = User.objects.create_user(username=f'staff_{Store.objects.count()}', password='pass')
    staff = Staff.objects.create(user=user, store=store, name='テストスタッフ')

    now = timezone.now()
    return Schedule.objects.create(
        staff=staff,
        store=store,
        start=now + datetime.timedelta(hours=24),
        end=now + datetime.timedelta(hours=25),
        is_temporary=is_temporary,
        is_cancelled=is_cancelled,
        price=price,
        cancel_token=cancel_token,
        booking_channel=booking_channel,
        customer_email=customer_email,
    )


# ---------------------------------------------------------------------------
# Webhook テスト
# ---------------------------------------------------------------------------

@override_settings(COINEY_WEBHOOK_TOKEN='test-webhook-token')
class TestCoineyWebhook(TestCase):
    """coiney_webhook ビューのテストスイート。"""

    def setUp(self):
        self.schedule = _create_confirmed_schedule(price=5000, is_temporary=True)
        self.order_id = str(self.schedule.reservation_number)
        self.webhook_url = f'/coiney_webhook/{self.order_id}/'
        self.valid_payload = json.dumps({'type': 'payment.succeeded'})

    # ------------------------------------------------------------------
    # 正常系
    # ------------------------------------------------------------------

    def test_valid_webhook_confirms_payment(self):
        """正常なトークンと payment.succeeded で予約が確定される。"""
        with patch('booking.services.checkin_token.generate_backup_code', return_value='123456'), \
             patch('booking.services.checkin_token.generate_signed_checkin_qr'), \
             patch('django.db.models.fields.files.FieldFile.save'), \
             patch('booking.services.staff_notifications.notify_booking_to_staff'), \
             patch('booking.views_booking._push_line_text'), \
             patch('booking.views_booking._make_messaging_api', return_value=(MagicMock(), MagicMock())):
            response = self.client.post(
                self.webhook_url + '?token=test-webhook-token',
                data=self.valid_payload,
                content_type='application/json',
            )

        assert response.status_code == 200
        data = response.json()
        assert data['status'] in ('success', 'already_processed')

        self.schedule.refresh_from_db()
        assert self.schedule.is_temporary is False

    def test_invalid_token_returns_403(self):
        """不正なトークンでリクエストすると 403 が返る。"""
        response = self.client.post(
            self.webhook_url + '?token=wrong-token',
            data=self.valid_payload,
            content_type='application/json',
        )

        assert response.status_code == 403
        assert response.json()['error'] == 'Invalid token'

    def test_missing_token_returns_403(self):
        """トークンなしのリクエストは 403 が返る。"""
        response = self.client.post(
            self.webhook_url,
            data=self.valid_payload,
            content_type='application/json',
        )

        assert response.status_code == 403

    # ------------------------------------------------------------------
    # 冪等性テスト
    # ------------------------------------------------------------------

    def test_duplicate_webhook_is_idempotent(self):
        """同一 orderId への重複 webhook は already_processed を返し副作用なし。"""
        # 事前に確定済みにしておく（is_temporary=False）
        already_confirmed = _create_confirmed_schedule(
            price=5000, is_temporary=False, cancel_token='CANCELA1'
        )
        order_id = str(already_confirmed.reservation_number)
        url = f'/coiney_webhook/{order_id}/?token=test-webhook-token'

        response = self.client.post(
            url,
            data=self.valid_payload,
            content_type='application/json',
        )

        assert response.status_code == 200
        assert response.json()['status'] == 'already_processed'

    # ------------------------------------------------------------------
    # バリデーション系
    # ------------------------------------------------------------------

    def test_non_post_method_returns_405(self):
        """GET リクエストは 405 を返す。"""
        response = self.client.get(
            self.webhook_url + '?token=test-webhook-token',
        )

        assert response.status_code == 405

    def test_wrong_content_type_returns_400(self):
        """Content-Type が application/json でない場合は 400 を返す。"""
        response = self.client.post(
            self.webhook_url + '?token=test-webhook-token',
            data=self.valid_payload,
            content_type='text/plain',
        )

        assert response.status_code == 400

    @override_settings(COINEY_WEBHOOK_TOKEN='')
    def test_unconfigured_token_returns_503(self):
        """COINEY_WEBHOOK_TOKEN 未設定時は 503 を返す。"""
        response = self.client.post(
            self.webhook_url,
            data=self.valid_payload,
            content_type='application/json',
        )

        assert response.status_code == 503


# ---------------------------------------------------------------------------
# 返金フロー テスト
# ---------------------------------------------------------------------------

class TestRefundFlow(TestCase):
    """CustomerCancelConfirmView の返金フローのテストスイート。"""

    # ------------------------------------------------------------------
    # 正常返金
    # ------------------------------------------------------------------

    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_email')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_staff_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_admin_email')
    def test_cancel_with_paid_price_sets_refund_pending(
        self, mock_admin, mock_customer_line, mock_staff_line, mock_customer_email
    ):
        """有料予約のキャンセルで refund_status が 'pending' になる。"""
        from booking.models import Schedule

        schedule = _create_confirmed_schedule(price=5000, cancel_token='CANCEL01')
        url = f'/cancel/{schedule.reservation_number}/confirm/'

        response = self.client.post(
            url,
            data={'cancel_token': 'CANCEL01'},
        )

        assert response.status_code == 200
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True
        assert schedule.refund_status == 'pending'

    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_email')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_staff_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_admin_email')
    def test_cancel_with_zero_price_does_not_set_refund(
        self, mock_admin, mock_customer_line, mock_staff_line, mock_customer_email
    ):
        """無料予約のキャンセルでは refund_status が 'none' のまま。"""
        schedule = _create_confirmed_schedule(price=0, cancel_token='CANCEL02')
        url = f'/cancel/{schedule.reservation_number}/confirm/'

        response = self.client.post(
            url,
            data={'cancel_token': 'CANCEL02'},
        )

        assert response.status_code == 200
        schedule.refresh_from_db()
        assert schedule.is_cancelled is True
        assert schedule.refund_status == 'none'

    # ------------------------------------------------------------------
    # エラーハンドリング
    # ------------------------------------------------------------------

    def test_wrong_cancel_token_returns_error_form(self):
        """誤ったキャンセルトークンではキャンセルされない。"""
        schedule = _create_confirmed_schedule(price=5000, cancel_token='CANCEL03')
        url = f'/cancel/{schedule.reservation_number}/confirm/'

        response = self.client.post(
            url,
            data={'cancel_token': 'WRONGTOK'},
        )

        assert response.status_code == 200
        schedule.refresh_from_db()
        assert schedule.is_cancelled is False

    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_email')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_staff_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_customer_line')
    @patch('booking.views_booking.CustomerCancelConfirmView._notify_admin_email')
    def test_already_cancelled_schedule_returns_done_page(
        self, mock_admin, mock_customer_line, mock_staff_line, mock_customer_email
    ):
        """既にキャンセル済みの予約は二重キャンセルされない。"""
        schedule = _create_confirmed_schedule(
            price=5000, cancel_token='CANCEL04', is_cancelled=True
        )
        url = f'/cancel/{schedule.reservation_number}/confirm/'

        response = self.client.post(
            url,
            data={'cancel_token': 'CANCEL04'},
        )

        assert response.status_code == 200
        # 返金ステータスは変わらず 'none' のまま（二重処理なし）
        schedule.refresh_from_db()
        assert schedule.refund_status == 'none'
