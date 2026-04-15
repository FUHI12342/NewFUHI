"""Tests for the unified Coiney payment service."""
import json
from unittest.mock import MagicMock, patch

import pytest
import requests

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
