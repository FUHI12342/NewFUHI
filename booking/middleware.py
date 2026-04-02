"""セキュリティ監視ミドルウェア + 言語固定ミドルウェア + メンテナンスミドルウェア"""
import threading
import time
import logging
from collections import defaultdict

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import translation

logger = logging.getLogger(__name__)


class MaintenanceMiddleware:
    """メンテナンスモード中は管理者以外に503を返す。
    AuthenticationMiddleware の後に配置すること（request.user を参照するため）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 管理者はバイパス
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)
        # ログインページもバイパス（管理者がログインできるように）
        if request.path.startswith('/admin/login'):
            return self.get_response(request)
        # ヘルスチェックもバイパス（デプロイスクリプトのヘルスチェック用）
        if request.path == '/healthz':
            return self.get_response(request)

        try:
            from booking.models import SiteSettings
            site_settings = SiteSettings.load()
        except Exception:
            return self.get_response(request)

        if site_settings.maintenance_mode:
            response = render(request, 'maintenance.html', {
                'message': site_settings.maintenance_message,
            }, status=503)
            response['Retry-After'] = '300'
            return response

        return self.get_response(request)


class ForceLanguageMiddleware:
    """SiteSettings.forced_language をサイトのデフォルト言語として適用。
    ユーザーが言語スイッチャーで明示的に選択した場合はそちらを優先する。

    優先順位:
    1. ユーザーの明示的選択（django_language Cookie — set_language ビューが設定）
    2. URLの言語プレフィックス（/en/、/zh-hant/ など）
    3. SiteSettings.forced_language（サイトデフォルト）
    4. Django の LANGUAGE_CODE 設定

    LocaleMiddleware の直後に配置。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            from booking.models import SiteSettings
            site_settings = SiteSettings.load()
        except Exception:
            return self.get_response(request)

        forced_lang = site_settings.forced_language if site_settings else ''

        if forced_lang:
            # ユーザーが言語スイッチャーで明示的に選択した場合（Cookie）を尊重
            user_cookie_lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
            # URLの言語プレフィックスも尊重
            lang_from_path = translation.get_language_from_path(request.path_info)

            if user_cookie_lang and translation.check_for_language(user_cookie_lang):
                # ユーザーの明示的選択を優先
                translation.activate(user_cookie_lang)
                request.LANGUAGE_CODE = user_cookie_lang
            elif lang_from_path:
                # URLプレフィックスの言語を優先（LocaleMiddleware で既に設定済み）
                pass
            else:
                # ユーザー選択もURLプレフィックスもない場合、forced_language を適用
                translation.activate(forced_lang)
                request.LANGUAGE_CODE = forced_lang

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

        # 5xxサーバーエラー通知
        if response.status_code >= 500:
            try:
                from booking.tasks import send_event_notification
                send_event_notification.delay(
                    'server_error', 'critical',
                    f'サーバーエラー {response.status_code}',
                    f'パス: {request.path}\nメソッド: {request.method}',
                    '',
                )
            except Exception:
                pass

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
        # Nginx sets X-Forwarded-For to $remote_addr (overwrites, not appends).
        # Use REMOTE_ADDR as primary — it's the actual TCP peer (Nginx).
        # X-Forwarded-For is only trusted because Nginx overwrites it.
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
            # Basic validation: reject obviously spoofed values
            if ip and ip.replace('.', '').replace(':', '').isalnum():
                return ip
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

            # 重要イベントは通知を送信
            if severity in ('critical', 'warning'):
                try:
                    from booking.tasks import send_event_notification
                    send_event_notification.delay(
                        'security_event', severity,
                        f'セキュリティ: {event_type}',
                        detail[:500],
                        '',
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.error('SecurityLog記録失敗: %s', e)
