"""X (Twitter) API v2 投稿サービス: OAuth 2.0 PKCE + トークンリフレッシュ"""
import logging
import time
from dataclasses import dataclass
from typing import Optional

import redis
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

X_API_BASE = 'https://api.x.com/2'
X_TOKEN_URL = 'https://api.x.com/2/oauth2/token'

# Redis分散ロック: トークンリフレッシュの排他制御
REFRESH_LOCK_TTL = 60  # 秒
TOKEN_EXPIRY_BUFFER = 300  # 期限の5分前にリフレッシュ

# HTTPタイムアウト
REQUEST_TIMEOUT = 30


class XApiError(Exception):
    """X API呼び出しエラーの基底クラス"""
    pass


class RateLimitError(XApiError):
    """429 Too Many Requests"""
    def __init__(self, reset_at=None):
        self.reset_at = reset_at
        super().__init__(f"Rate limited until {reset_at}")


class TokenExpiredError(XApiError):
    """401 Unauthorized (トークン期限切れ)"""
    pass


class RetryableError(XApiError):
    """5xx サーバーエラー (リトライ可能)"""
    pass


@dataclass
class PostResult:
    success: bool
    external_post_id: str = ''
    error_message: str = ''
    rate_limit_remaining: Optional[int] = None
    rate_limit_reset: Optional[int] = None


def _get_redis():
    """Celery broker URL からRedisクライアントを取得"""
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def _is_token_expiring(social_account):
    """トークンが期限切れまたは5分以内に期限切れになるか"""
    if not social_account.token_expires_at:
        return True
    buffer = timezone.timedelta(seconds=TOKEN_EXPIRY_BUFFER)
    return timezone.now() + buffer >= social_account.token_expires_at


def refresh_x_token(social_account):
    """X OAuth 2.0 トークンリフレッシュ（Redis分散ロック付き）

    X のリフレッシュトークンはワンタイム使用。
    複数ワーカーが同時にリフレッシュすると全トークンが無効化される。
    """
    lock_key = f'x_api:token_refresh:{social_account.id}'
    try:
        r = _get_redis()
    except Exception as e:
        logger.error("Redis unavailable for token refresh lock: %s", e)
        raise XApiError(f"Redis unavailable: {e}")

    # Redis分散ロック取得 (NX + EX)
    acquired = r.set(lock_key, '1', nx=True, ex=REFRESH_LOCK_TTL)
    if not acquired:
        logger.info(
            "Token refresh already in progress for account %s, waiting...",
            social_account.id,
        )
        # 他のワーカーがリフレッシュ中。最大60秒待って再読み込み
        for _ in range(12):
            time.sleep(5)
            social_account.refresh_from_db()
            if not _is_token_expiring(social_account):
                return  # 他のワーカーがリフレッシュ成功
        raise XApiError("Token refresh lock timeout")

    try:
        response = requests.post(
            X_TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'refresh_token': social_account.refresh_token,
                'client_id': settings.X_CLIENT_ID,
            },
            auth=(settings.X_CLIENT_ID, settings.X_CLIENT_SECRET),
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            error_body = response.text[:500]
            logger.error(
                "Token refresh failed for account %s: %s %s",
                social_account.id, response.status_code, error_body,
            )
            raise XApiError(f"Token refresh failed: {response.status_code}")

        data = response.json()
        social_account.access_token = data['access_token']
        social_account.refresh_token = data['refresh_token']
        social_account.token_expires_at = (
            timezone.now() + timezone.timedelta(seconds=data.get('expires_in', 7200))
        )
        try:
            social_account.save(
                update_fields=['access_token', 'refresh_token', 'token_expires_at', 'updated_at'],
            )
        except Exception as db_exc:
            logger.critical(
                "Token refresh received from X but DB save failed for account %s. "
                "Account requires manual re-authorization. DB error: %s",
                social_account.id, db_exc,
            )
            raise XApiError(f"Token DB save failed: {db_exc}") from db_exc
        logger.info("Token refreshed for account %s", social_account.id)

    finally:
        r.delete(lock_key)


def post_tweet(social_account, content):
    """X API v2 でツイートを投稿。PostResult を返す。"""
    # 1. トークン期限チェック
    if _is_token_expiring(social_account):
        try:
            refresh_x_token(social_account)
        except XApiError:
            logger.warning(
                "Token refresh failed before posting for account %s",
                social_account.id,
            )
            raise

    # 2. POST /2/tweets
    headers = {
        'Authorization': f'Bearer {social_account.access_token}',
        'Content-Type': 'application/json',
    }
    payload = {'text': content}

    try:
        response = requests.post(
            f'{X_API_BASE}/tweets',
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        raise RetryableError("Request timeout")
    except requests.exceptions.ConnectionError as e:
        raise RetryableError(f"Connection error: {e}")

    # 3. レスポンス解析
    rate_remaining = response.headers.get('x-rate-limit-remaining')
    rate_reset = response.headers.get('x-rate-limit-reset')

    if response.status_code == 201:
        data = response.json()
        tweet_id = data.get('data', {}).get('id', '')
        return PostResult(
            success=True,
            external_post_id=tweet_id,
            rate_limit_remaining=int(rate_remaining) if rate_remaining else None,
            rate_limit_reset=int(rate_reset) if rate_reset else None,
        )

    if response.status_code == 429:
        reset_at = int(rate_reset) if rate_reset else None
        raise RateLimitError(reset_at=reset_at)

    if response.status_code == 401:
        # トークン期限切れ → リフレッシュして1回だけリトライ
        try:
            refresh_x_token(social_account)
        except XApiError:
            raise TokenExpiredError("Token refresh failed on 401")

        headers['Authorization'] = f'Bearer {social_account.access_token}'
        retry_resp = requests.post(
            f'{X_API_BASE}/tweets',
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if retry_resp.status_code == 201:
            data = retry_resp.json()
            return PostResult(
                success=True,
                external_post_id=data.get('data', {}).get('id', ''),
            )
        raise TokenExpiredError(f"Retry after refresh failed: {retry_resp.status_code}")

    if response.status_code >= 500:
        raise RetryableError(f"Server error: {response.status_code}")

    # その他のエラー (403等)
    error_body = response.text[:500]
    logger.error("X API error %s: %s", response.status_code, error_body)
    raise XApiError(f"X API error {response.status_code}")


def validate_x_credentials(social_account):
    """X API 接続確認。GET /2/users/me でユーザー情報を取得。"""
    if _is_token_expiring(social_account):
        try:
            refresh_x_token(social_account)
        except XApiError:
            return False

    headers = {
        'Authorization': f'Bearer {social_account.access_token}',
    }
    try:
        response = requests.get(
            f'{X_API_BASE}/users/me',
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        return response.status_code == 200
    except Exception:
        return False
