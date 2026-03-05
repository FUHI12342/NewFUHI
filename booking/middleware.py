"""セキュリティ監視ミドルウェア"""
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


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
    _MAX_ENTRIES = 10000
    _RATE_WINDOW = 60  # seconds
    _RATE_THRESHOLD = 100

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ip = self._get_client_ip(request)

        # レートリミットチェック（リクエスト前）
        self._check_rate_limit(request, ip)

        response = self.get_response(request)

        # ログイン結果の判定
        if request.method == 'POST' and '/login/' in request.path:
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
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _check_rate_limit(self, request, ip):
        now = time.time()

        # エントリ数上限チェック
        if len(self._rate_counter) > self._MAX_ENTRIES:
            self._rate_counter.clear()

        # 古いエントリを削除
        timestamps = self._rate_counter[ip]
        cutoff = now - self._RATE_WINDOW
        self._rate_counter[ip] = [t for t in timestamps if t > cutoff]
        self._rate_counter[ip].append(now)

        if len(self._rate_counter[ip]) > self._RATE_THRESHOLD:
            self._log_event(
                event_type='suspicious_request',
                severity='critical',
                request=request,
                ip=ip,
                detail=f'レートリミット超過: {ip} から60秒以内に{len(self._rate_counter[ip])}リクエスト',
            )

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

            SecurityLog.objects.create(
                event_type=event_type,
                severity=severity,
                user=user,
                username=getattr(user, 'username', '') if user else request.POST.get('username', ''),
                ip_address=ip,
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                path=request.path[:500],
                method=request.method,
                detail=detail,
            )
        except Exception as e:
            logger.error('SecurityLog記録失敗: %s', e)
