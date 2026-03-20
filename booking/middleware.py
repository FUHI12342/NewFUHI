"""セキュリティ監視ミドルウェア + 言語固定ミドルウェア"""
import threading
import time
import logging
from collections import defaultdict

from django.conf import settings
from django.http import JsonResponse
from django.utils import translation

LANGUAGE_SESSION_KEY = '_language'

logger = logging.getLogger(__name__)


class ForceLanguageMiddleware:
    """SiteSettings.forced_language が設定されていればその言語を強制適用。
    URLに言語プレフィックスがある場合はセッションに保存して維持する。
    LocaleMiddleware の直後に配置。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from booking.models import SiteSettings
            site_settings = SiteSettings.load()
            if site_settings.forced_language:
                translation.activate(site_settings.forced_language)
                request.LANGUAGE_CODE = site_settings.forced_language
                return self.get_response(request)
        except Exception:
            pass

        # URLプレフィックスから言語を検出した場合、セッションに保存
        lang_from_url = getattr(request, 'LANGUAGE_CODE', None)
        if lang_from_url and hasattr(request, 'session'):
            stored_lang = request.session.get(LANGUAGE_SESSION_KEY)
            if lang_from_url != settings.LANGUAGE_CODE and lang_from_url != stored_lang:
                request.session[LANGUAGE_SESSION_KEY] = lang_from_url
            elif lang_from_url == settings.LANGUAGE_CODE and stored_lang:
                # デフォルト言語に戻った場合、セッションの言語設定をクリア
                request.session.pop(LANGUAGE_SESSION_KEY, None)

        return self.get_response(request)


class SecurityAuditMiddleware:
    """
    全リクエストを監視し、セキュリティイベントをSecurityLogに記録する。

    - ログイン成功/失敗: /login/ へのPOSTの結果を判定
    - API認証失敗: /api/ パスで401/403レスポンス
    - 権限拒否: 403レスポンス
    - 不審なリクエスト: 同一IPから60秒以内に100リクエスト超
    """

    # インメモリレートカウンター（10,000エントリ上限で自動クリーン）
    _rate_counter = defaultdict(list)
    _rate_lock = threading.Lock()
    _MAX_ENTRIES = 10000
    _RATE_WINDOW = 60  # seconds
    _RATE_THRESHOLD = 100

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self._get_client_ip(request)

        # レートリミットチェック（リクエスト前）— 超過時は429で即ブロック
        blocked = self._check_rate_limit(request, ip)
        if blocked:
            return blocked

        response = self.get_response(request)

        # ログイン結果の判定
        if request.method == 'POST' and request.path.endswith('/login/'):
            self._handle_login_result(request, response, ip)

        # API認証失敗
        if '/api/' in request.path and response.status_code in (401, 403):
            self._log_event(
                event_type='api_auth_fail',
                severity='warning',
                request=request,
                ip=ip,
                detail=f'API認証失敗: {request.path} (HTTP {response.status_code})',
            )

        # 権限拒否（API以外）
        elif '/api/' not in request.path and response.status_code == 403:
            self._log_event(
                event_type='permission_denied',
                severity='warning',
                request=request,
                ip=ip,
                detail=f'権限拒否: {request.path}',
            )

        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # First entry is the original client IP
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _check_rate_limit(self, request, ip):
        if getattr(settings, 'TESTING', False):
            return None
        now = time.time()

        with self._rate_lock:
            # エントリ数上限チェック
            if len(self._rate_counter) > self._MAX_ENTRIES:
                self._rate_counter.clear()

            # 古いエントリを削除
            cutoff = now - self._RATE_WINDOW
            self._rate_counter[ip] = [t for t in self._rate_counter[ip] if t > cutoff]
            self._rate_counter[ip].append(now)
            count = len(self._rate_counter[ip])

        if count > self._RATE_THRESHOLD:
            self._log_event(
                event_type='suspicious_request',
                severity='critical',
                request=request,
                ip=ip,
                detail=f'レートリミット超過: {ip} から60秒以内に{count}リクエスト',
            )
            retry_after = self._RATE_WINDOW
            return JsonResponse(
                {'error': 'Too many requests. Please try again later.'},
                status=429,
                headers={'Retry-After': str(retry_after)},
            )
        return None

    def _handle_login_result(self, request, response, ip):
        if response.status_code in (200, 302):
            if hasattr(request, 'user') and request.user.is_authenticated:
                self._log_event(
                    event_type='login_success',
                    severity='info',
                    request=request,
                    ip=ip,
                    detail='ログイン成功',
                )
            elif response.status_code == 302 and '/admin/' not in request.path:
                # 302リダイレクトはログイン成功の可能性
                self._log_event(
                    event_type='login_success',
                    severity='info',
                    request=request,
                    ip=ip,
                    detail='ログイン成功（リダイレクト）',
                )
            else:
                self._log_event(
                    event_type='login_fail',
                    severity='warning',
                    request=request,
                    ip=ip,
                    detail='ログイン失敗',
                )
        elif response.status_code >= 400:
            self._log_event(
                event_type='login_fail',
                severity='warning',
                request=request,
                ip=ip,
                detail=f'ログイン失敗 (HTTP {response.status_code})',
            )

    def _log_event(self, event_type, severity, request, ip, detail):
        try:
            from booking.models import SecurityLog
            user = getattr(request, 'user', None)
            if user and not user.is_authenticated:
                user = None

            # Truncate POST username to limit exposure if user typed password in username field
            raw_username = getattr(user, 'username', '') if user else request.POST.get('username', '')
            safe_username = (raw_username or '')[:100]

            SecurityLog.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                username=safe_username,
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                path=request.path[:500],
                method=request.method,
                detail=detail,
            )
        except Exception as e:
            logger.error('SecurityLog記録失敗: %s', e)
