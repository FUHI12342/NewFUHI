"""統一決済サービス: Coiney API連携"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class CoineyPaymentError(Exception):
    """Coiney API呼び出しの失敗"""
    pass


def create_payment_link(
    *,
    amount: int,
    subject: str,
    description: str,
    remarks: str,
    reservation_number: str,
    webhook_token: str,
    webhook_url_base: str = '',
    expired_on: str = '',
    cancel_url: str = '',
    metadata: dict = None,
    api_url: str = '',
    api_key: str = '',
):
    """Coiney決済リンクを作成する。

    Args:
        amount: 決済金額（円）
        subject: 決済タイトル
        description: 決済説明
        remarks: 備考
        reservation_number: Webhook URLに埋め込む予約識別子
        webhook_token: Webhook認証トークン（空文字の場合はクエリなし）
        webhook_url_base: WebhookのベースURL（省略時はsettings.WEBHOOK_URL_BASE）
        expired_on: 決済リンク有効期限（YYYY-MM-DD形式、省略時は期限なし）
        cancel_url: キャンセル時のリダイレクトURL（省略時はsettings.CANCEL_URL）
        metadata: metadataフィールド（省略時は {"orderId": reservation_number}）
        api_url: Coiney APIエンドポイント（省略時はsettings.PAYMENT_API_URL）
        api_key: Coiney APIキー（省略時はsettings.PAYMENT_API_KEY）

    Returns:
        決済URL文字列、またはAPI未設定・失敗時はNone

    Raises:
        CoineyPaymentError: API呼び出し失敗時（呼び出し元がエラー処理を行う場合）
    """
    payment_api_url = api_url or getattr(settings, 'PAYMENT_API_URL', '')
    payment_api_key = api_key or getattr(settings, 'PAYMENT_API_KEY', '')

    if not payment_api_url or not payment_api_key:
        logger.info("Coiney API未設定: PAYMENT_API_URL or PAYMENT_API_KEY missing")
        return None

    _wb_base = webhook_url_base or getattr(settings, 'WEBHOOK_URL_BASE', '')
    _wh_token = f"?token={webhook_token}" if webhook_token else ""
    webhook_url = f"{_wb_base}{reservation_number}/{_wh_token}"

    _cancel_url = cancel_url or getattr(settings, 'CANCEL_URL', '')
    _metadata = metadata if metadata is not None else {"orderId": str(reservation_number)}

    headers = {
        'Authorization': f'Bearer {payment_api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CoineyPayge-Version': '2016-10-25',
    }

    data = {
        "amount": amount,
        "currency": "jpy",
        "locale": "ja_JP",
        "cancelUrl": _cancel_url,
        "webhookUrl": webhook_url,
        "method": "creditcard",
        "subject": subject,
        "description": description,
        "remarks": remarks,
        "metadata": _metadata,
    }
    if expired_on:
        data["expiredOn"] = expired_on

    try:
        response = requests.post(
            payment_api_url,
            headers=headers,
            data=json.dumps(data),
            timeout=30,
        )
        if response.status_code == 201:
            payment_url = response.json().get('links', {}).get('paymentUrl')
            if payment_url:
                logger.info("Coiney決済リンク作成成功: reservation=%s", reservation_number)
                return payment_url
            logger.error(
                "Coiney API: paymentUrlが応答に含まれない: reservation=%s, body=%s",
                reservation_number, response.text,
            )
        else:
            logger.error(
                "Coiney API失敗: status=%s, reservation=%s, body=%s",
                response.status_code, reservation_number, response.text,
            )
    except requests.RequestException as e:
        logger.error("Coiney API呼び出し失敗: %s", e)
        raise CoineyPaymentError(f"決済リンク作成失敗: {e}") from e

    return None
