"""Tests for SecurityAuditMiddleware."""
import time
import pytest
from unittest.mock import MagicMock, patch
from django.test import RequestFactory, override_settings
from django.contrib.auth.models import User, AnonymousUser
from django.http import HttpResponse

from booking.middleware import SecurityAuditMiddleware
from booking.models import SecurityLog


@pytest.fixture
def rf():
    """Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
def middleware():
    """Create SecurityAuditMiddleware with a simple get_response."""
    def get_response(request):
        return HttpResponse(status=200)
    mw = SecurityAuditMiddleware(get_response)
    # Clear rate counter between tests
    mw._rate_counter.clear()
    return mw


class TestSecurityAuditMiddleware:
    """Tests for SecurityAuditMiddleware."""

    @pytest.mark.django_db
    def test_logs_login_success(self, rf):
        """Logs login_success on POST /login/ with 302 and authenticated user."""
        user = User.objects.create_user(username='testlogin', password='pass')

        def get_response(request):
            request.user = user
            return HttpResponse(status=302)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.post('/login/', {'username': 'testlogin', 'password': 'pass'})
        request.user = user
        request.META['REMOTE_ADDR'] = '10.0.0.1'

        mw(request)
        log = SecurityLog.objects.filter(event_type='login_success').last()
        assert log is not None

    @pytest.mark.django_db
    def test_logs_login_failure(self, rf):
        """Logs login_fail on POST /login/ with 200 and non-authenticated user."""
        def get_response(request):
            return HttpResponse(status=200)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.post('/login/', {'username': 'bad', 'password': 'wrong'})
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.2'

        mw(request)
        log = SecurityLog.objects.filter(event_type='login_fail').last()
        assert log is not None

    @pytest.mark.django_db
    def test_logs_api_auth_fail_401(self, rf, middleware):
        """Logs api_auth_fail on /api/ path with 401 response."""
        def get_response(request):
            return HttpResponse(status=401)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.get('/api/sensors/')
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.3'

        mw(request)
        log = SecurityLog.objects.filter(event_type='api_auth_fail').last()
        assert log is not None

    @pytest.mark.django_db
    def test_logs_api_auth_fail_403(self, rf):
        """Logs api_auth_fail on /api/ path with 403 response."""
        def get_response(request):
            return HttpResponse(status=403)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.get('/api/admin/')
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.4'

        mw(request)
        log = SecurityLog.objects.filter(event_type='api_auth_fail').last()
        assert log is not None

    @pytest.mark.django_db
    def test_logs_permission_denied_non_api(self, rf):
        """Logs permission_denied on non-API 403 response."""
        def get_response(request):
            return HttpResponse(status=403)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.get('/admin/booking/')
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.5'

        mw(request)
        log = SecurityLog.objects.filter(event_type='permission_denied').last()
        assert log is not None

    @pytest.mark.django_db
    @override_settings(TESTING=False)
    def test_rate_limit_suspicious_request(self, rf):
        """Logs suspicious_request when >100 requests from same IP in 60s."""
        def get_response(request):
            return HttpResponse(status=200)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        ip = '10.0.0.99'
        for i in range(102):
            request = rf.get(f'/page/{i}/')
            request.user = AnonymousUser()
            request.META['REMOTE_ADDR'] = ip
            mw(request)

        logs = SecurityLog.objects.filter(event_type='suspicious_request')
        assert logs.exists()

    @pytest.mark.django_db
    def test_get_client_ip_x_forwarded_for(self, rf, middleware):
        """_get_client_ip reads leftmost (client) IP from X-Forwarded-For."""
        request = rf.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.50, 70.41.3.18'
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        ip = middleware._get_client_ip(request)
        assert ip == '203.0.113.50'

    @pytest.mark.django_db
    def test_get_client_ip_remote_addr_fallback(self, rf, middleware):
        """_get_client_ip falls back to REMOTE_ADDR when no X-Forwarded-For."""
        request = rf.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        if 'HTTP_X_FORWARDED_FOR' in request.META:
            del request.META['HTTP_X_FORWARDED_FOR']
        ip = middleware._get_client_ip(request)
        assert ip == '192.168.1.100'

    @pytest.mark.django_db
    def test_normal_request_no_security_log(self, rf):
        """Normal GET request to non-login, non-API path does not create security log."""
        def get_response(request):
            return HttpResponse(status=200)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        initial_count = SecurityLog.objects.count()
        request = rf.get('/booking/')
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.50'
        mw(request)
        assert SecurityLog.objects.count() == initial_count

    @pytest.mark.django_db
    def test_login_post_400_logs_failure(self, rf):
        """POST to /login/ returning 400+ logs login_fail."""
        def get_response(request):
            return HttpResponse(status=400)

        mw = SecurityAuditMiddleware(get_response)
        mw._rate_counter.clear()

        request = rf.post('/login/')
        request.user = AnonymousUser()
        request.META['REMOTE_ADDR'] = '10.0.0.60'
        mw(request)

        log = SecurityLog.objects.filter(event_type='login_fail').last()
        assert log is not None
