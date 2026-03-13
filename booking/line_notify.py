import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_line_notify(message: str, max_retries: int = 3) -> bool:
    """
    LINE Notify APIを使ってメッセージを送信（リトライ付き）。

    .env.local / .env.production / .env から LINE_NOTIFY_TOKEN を読み込む。
    429 (Rate Limited) やネットワークエラー時は指数バックオフでリトライ。
    失敗しても例外を投げず、Falseを返す。
    """
    token = getattr(settings, 'LINE_NOTIFY_TOKEN', None)
    if not token:
        logger.warning("LINE_NOTIFY_TOKEN is not set")
        return False

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                'https://notify-api.line.me/api/notify',
                headers={'Authorization': f'Bearer {token}'},
                data={'message': message},
                timeout=10,
            )
            if resp.status_code == 200:
                return True
            if resp.status_code == 429:  # Rate limited
                logger.warning("LINE notify rate limited (429), retrying in %ds", 2 ** attempt)
                time.sleep(2 ** attempt)
                continue
            logger.warning("LINE notify failed: %d %s", resp.status_code, resp.text)
            return False
        except requests.RequestException as e:
            logger.warning("LINE notify attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return False
