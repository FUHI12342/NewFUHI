"""X (Twitter) OAuth 2.0 PKCE 認証フロー"""
import hashlib
import logging
import secrets

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

logger = logging.getLogger(__name__)

X_AUTHORIZE_URL = 'https://x.com/i/oauth2/authorize'
X_TOKEN_URL = 'https://api.x.com/2/oauth2/token'
X_USERS_ME_URL = 'https://api.x.com/2/users/me'

SCOPES = 'tweet.read tweet.write users.read offline.access'
REQUEST_TIMEOUT = 30


def _generate_code_verifier():
    """PKCE code_verifier を生成 (43-128文字のランダム文字列)"""
    return secrets.token_urlsafe(64)[:128]


def _generate_code_challenge(verifier):
    """PKCE code_challenge を生成 (S256)"""
    import base64
    digest = hashlib.sha256(verifier.encode('ascii')).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


@method_decorator(staff_member_required, name='dispatch')
class XConnectView(View):
    """Step 1: X OAuth認証画面へリダイレクト"""

    def get(self, request):
        store_id = request.GET.get('store_id')
        if not store_id:
            return HttpResponseBadRequest('store_id is required')

        # PKCE パラメータ生成
        state = secrets.token_urlsafe(32)
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)

        # セッションに保存
        request.session['x_oauth_state'] = state
        request.session['x_oauth_code_verifier'] = code_verifier
        request.session['x_oauth_store_id'] = store_id

        params = {
            'response_type': 'code',
            'client_id': settings.X_CLIENT_ID,
            'redirect_uri': settings.X_REDIRECT_URI,
            'scope': SCOPES,
            'state': state,
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }
        query = '&'.join(f'{k}={requests.utils.quote(str(v))}' for k, v in params.items())
        authorize_url = f'{X_AUTHORIZE_URL}?{query}'
        return redirect(authorize_url)


@method_decorator(staff_member_required, name='dispatch')
class XCallbackView(View):
    """Step 2: X OAuth コールバック処理"""

    def get(self, request):
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')

        if error:
            known_errors = {
                'access_denied': 'X連携が拒否されました',
                'invalid_request': 'X連携リクエストが不正です',
                'server_error': 'X側でエラーが発生しました',
            }
            safe_msg = known_errors.get(error, 'X連携エラーが発生しました')
            messages.error(request, safe_msg)
            logger.warning("X OAuth error: %s", error)
            return redirect('/admin/')

        # State検証
        expected_state = request.session.pop('x_oauth_state', None)
        if not state or state != expected_state:
            messages.error(request, 'X連携エラー: state不一致')
            logger.warning("X OAuth state mismatch")
            return redirect('/admin/')

        code_verifier = request.session.pop('x_oauth_code_verifier', None)
        store_id = request.session.pop('x_oauth_store_id', None)

        if not code or not code_verifier or not store_id:
            messages.error(request, 'X連携エラー: セッション情報不足')
            return redirect('/admin/')

        # トークン取得
        token_data = self._exchange_code(code, code_verifier)
        if not token_data:
            messages.error(request, 'X連携エラー: トークン取得失敗')
            return redirect('/admin/')

        # ユーザー情報取得
        username = self._get_username(token_data['access_token'])
        if not username:
            messages.error(request, 'X連携エラー: ユーザー情報取得失敗')
            return redirect('/admin/')

        # SocialAccount 作成/更新
        self._save_social_account(
            store_id=store_id,
            username=username,
            token_data=token_data,
        )

        messages.success(request, f'X連携完了: @{username}')
        return redirect('/admin/booking/socialaccount/')

    def _exchange_code(self, code, code_verifier):
        """認証コードをアクセストークンに交換"""
        try:
            response = requests.post(
                X_TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': settings.X_REDIRECT_URI,
                    'code_verifier': code_verifier,
                    'client_id': settings.X_CLIENT_ID,
                },
                auth=(settings.X_CLIENT_ID, settings.X_CLIENT_SECRET),
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                logger.error(
                    "X token exchange failed: %s %s",
                    response.status_code, response.text[:500],
                )
                return None
            return response.json()
        except Exception as e:
            logger.error("X token exchange error: %s", e)
            return None

    def _get_username(self, access_token):
        """GET /2/users/me でユーザー名を取得"""
        try:
            response = requests.get(
                X_USERS_ME_URL,
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code != 200:
                logger.error("X users/me failed: %s", response.status_code)
                return None
            return response.json().get('data', {}).get('username')
        except Exception as e:
            logger.error("X users/me error: %s", e)
            return None

    def _save_social_account(self, store_id, username, token_data):
        """SocialAccount を作成または更新"""
        from booking.models import SocialAccount

        expires_in = token_data.get('expires_in', 7200)
        token_expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)

        account, created = SocialAccount.objects.update_or_create(
            store_id=store_id,
            platform='x',
            defaults={
                'account_name': username,
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', ''),
                'token_expires_at': token_expires_at,
                'is_active': True,
            },
        )
        action = 'created' if created else 'updated'
        logger.info("SocialAccount %s for store %s: @%s", action, store_id, username)
