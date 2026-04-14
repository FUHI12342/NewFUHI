"""TikTok Content Posting API サービス — OAuth 2.0 + 動画投稿"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

TIKTOK_TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'
TIKTOK_USERINFO_URL = 'https://open.tiktokapis.com/v2/user/info/'
TIKTOK_UPLOAD_INIT_URL = 'https://open.tiktokapis.com/v2/post/publish/inbox/video/init/'
TIKTOK_PUBLISH_STATUS_URL = 'https://open.tiktokapis.com/v2/post/publish/status/fetch/'

REQUEST_TIMEOUT = 30


class TikTokApiError(Exception):
    """TikTok API エラー"""


class TikTokPostResult:
    """TikTok 投稿結果"""

    def __init__(self, success, publish_id='', error_message=''):
        self.success = success
        self.publish_id = publish_id
        self.error_message = error_message


def exchange_code_for_token(code, redirect_uri):
    """認証コードをアクセストークンに交換

    Args:
        code: OAuth 認証コード
        redirect_uri: リダイレクト URI

    Returns:
        dict with access_token, refresh_token, etc. or None
    """
    client_key = getattr(settings, 'TIKTOK_CLIENT_KEY', '')
    client_secret = getattr(settings, 'TIKTOK_CLIENT_SECRET', '')
    if not client_key or not client_secret:
        logger.error('TIKTOK_CLIENT_KEY or TIKTOK_CLIENT_SECRET not configured')
        return None

    payload = json.dumps({
        'client_key': client_key,
        'client_secret': client_secret,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
    }).encode('utf-8')

    req = urllib.request.Request(
        TIKTOK_TOKEN_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'access_token' in data:
                return data
            logger.error("TikTok token exchange failed: %s", data)
            return None
    except Exception as e:
        logger.error("TikTok token exchange error: %s", e)
        return None


def refresh_access_token(refresh_token):
    """リフレッシュトークンでアクセストークンを更新

    Args:
        refresh_token: リフレッシュトークン

    Returns:
        dict with new access_token, etc. or None
    """
    client_key = getattr(settings, 'TIKTOK_CLIENT_KEY', '')
    client_secret = getattr(settings, 'TIKTOK_CLIENT_SECRET', '')

    payload = json.dumps({
        'client_key': client_key,
        'client_secret': client_secret,
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    }).encode('utf-8')

    req = urllib.request.Request(
        TIKTOK_TOKEN_URL,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'access_token' in data:
                return data
            logger.error("TikTok token refresh failed: %s", data)
            return None
    except Exception as e:
        logger.error("TikTok token refresh error: %s", e)
        return None


def get_user_info(access_token):
    """TikTok ユーザー情報を取得

    Args:
        access_token: アクセストークン

    Returns:
        dict with display_name, username, etc. or None
    """
    payload = json.dumps({
        'fields': 'open_id,union_id,display_name,avatar_url',
    }).encode('utf-8')

    req = urllib.request.Request(
        TIKTOK_USERINFO_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            user_data = data.get('data', {}).get('user', {})
            if user_data:
                return user_data
            logger.error("TikTok user info failed: %s", data)
            return None
    except Exception as e:
        logger.error("TikTok user info error: %s", e)
        return None


def init_video_upload(account, video_url=None, video_size=None):
    """動画投稿を初期化（Content Posting API — inbox upload）

    TikTok Content Posting API は以下のフローで動画を投稿:
    1. init_video_upload() で publish_id を取得
    2. ユーザーが TikTok アプリで投稿を確認・公開

    Args:
        account: SocialAccount インスタンス
        video_url: 動画の公開URL (source_info.source = 'PULL_FROM_URL')
        video_size: 動画ファイルサイズ (bytes)

    Returns:
        TikTokPostResult
    """
    access_token = account.access_token
    if not access_token:
        return TikTokPostResult(
            success=False, error_message='アクセストークンが設定されていません',
        )

    # トークン期限チェック
    if account.token_expires_at and account.token_expires_at <= timezone.now():
        refreshed = _try_refresh_token(account)
        if not refreshed:
            return TikTokPostResult(
                success=False, error_message='トークン期限切れ・リフレッシュ失敗',
            )
        access_token = account.access_token

    if not video_url:
        return TikTokPostResult(
            success=False, error_message='動画URLが指定されていません',
        )

    body = {
        'post_info': {
            'title': '',  # タイトルは TikTok アプリで設定
            'privacy_level': 'SELF_ONLY',  # 初期は非公開
        },
        'source_info': {
            'source': 'PULL_FROM_URL',
            'video_url': video_url,
        },
    }
    if video_size:
        body['source_info']['video_size'] = video_size

    payload = json.dumps(body).encode('utf-8')

    req = urllib.request.Request(
        TIKTOK_UPLOAD_INIT_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        error_data = data.get('error', {})
        if error_data.get('code') != 'ok':
            error_msg = error_data.get('message', 'Unknown error')
            logger.error("TikTok upload init failed: %s", error_msg)
            return TikTokPostResult(success=False, error_message=error_msg)

        publish_id = data.get('data', {}).get('publish_id', '')
        logger.info("TikTok upload initiated: publish_id=%s", publish_id)
        return TikTokPostResult(success=True, publish_id=publish_id)

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        logger.error("TikTok upload init HTTP error %d: %s", e.code, error_body[:500])
        raise TikTokApiError(f'HTTP {e.code}: {error_body[:200]}')
    except Exception as e:
        logger.error("TikTok upload init error: %s", e)
        raise TikTokApiError(str(e))


def check_publish_status(account, publish_id):
    """投稿ステータスを確認

    Args:
        account: SocialAccount インスタンス
        publish_id: 投稿 ID

    Returns:
        dict with status info or None
    """
    payload = json.dumps({'publish_id': publish_id}).encode('utf-8')

    req = urllib.request.Request(
        TIKTOK_PUBLISH_STATUS_URL,
        data=payload,
        headers={
            'Authorization': f'Bearer {account.access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        logger.error("TikTok publish status check error: %s", e)
        return None


def _try_refresh_token(account):
    """トークンのリフレッシュを試行し、成功時は SocialAccount を更新"""
    if not account.refresh_token:
        return False

    token_data = refresh_access_token(account.refresh_token)
    if not token_data:
        return False

    account.access_token = token_data['access_token']
    account.refresh_token = token_data.get('refresh_token', account.refresh_token)
    expires_in = token_data.get('expires_in', 86400)
    account.token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
    account.save(update_fields=[
        'access_token', 'refresh_token', 'token_expires_at', 'updated_at',
    ])
    logger.info("TikTok token refreshed for account %s", account.account_name)
    return True
