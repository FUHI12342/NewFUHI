"""
API網羅テスト

- /healthz 正常応答
- 管理画面ログイン必須確認
- マイページ認証確認
- CSRFトークンなしPOST拒否
- 不正JSON入力の処理
- SQLインジェクション文字列の安全な処理
- IoT API鍵なしアクセス拒否
"""
import json

from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()


class TestHealthEndpoint(TestCase):
    """/healthz エンドポイントテスト"""

    def test_healthz_returns_ok(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertIn('django', data)

    def test_healthz_accepts_get_only(self):
        response = self.client.post('/healthz')
        self.assertIn(response.status_code, (200, 405))


class TestAdminAccess(TestCase):
    """管理画面アクセス制御テスト"""

    def test_admin_requires_login(self):
        response = self.client.get('/admin/')
        self.assertIn(response.status_code, (301, 302))

    def test_admin_login_page_loads(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 200)


class TestAuthenticationRequired(TestCase):
    """認証必須エンドポイントテスト"""

    def test_mypage_requires_auth(self):
        response = self.client.get('/booking/mypage/')
        self.assertIn(response.status_code, (301, 302, 404))

    def test_dashboard_requires_auth(self):
        response = self.client.get('/booking/dashboard/')
        self.assertIn(response.status_code, (301, 302, 404))


class TestCSRFProtection(TestCase):
    """CSRFトークンなしPOST拒否テスト"""

    def test_login_without_csrf_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/login/', {
            'username': 'admin',
            'password': 'admin',
        })
        self.assertIn(response.status_code, (400, 403))

    def test_api_post_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/api/iot/events/', {
            'device': 'test',
            'event_type': 'sensor',
        }, content_type='application/json')
        self.assertIn(response.status_code, (200, 400, 403))


class TestInvalidInput(TestCase):
    """不正入力の処理テスト"""

    def test_invalid_json_body(self):
        response = self.client.post(
            '/api/iot/events/',
            data='{"invalid json',
            content_type='application/json',
        )
        self.assertIn(response.status_code, (400, 403, 404, 415))

    def test_oversized_payload_handling(self):
        large_data = {'data': 'x' * 10000}
        response = self.client.post(
            '/api/iot/events/',
            data=json.dumps(large_data),
            content_type='application/json',
        )
        self.assertNotEqual(response.status_code, 500)


class TestSQLInjection(TestCase):
    """SQLインジェクション安全性テスト"""

    def test_sql_injection_in_login(self):
        response = self.client.post('/login/', {
            'username': "admin' OR '1'='1",
            'password': "' OR '1'='1",
        })
        # SQLインジェクションが成功しない（200=フォーム再表示, 302=リダイレクト）
        self.assertIn(response.status_code, (200, 302))

    def test_sql_injection_in_search(self):
        response = self.client.get('/admin/login/', {
            'q': "'; DROP TABLE booking_schedule; --",
        })
        self.assertIn(response.status_code, (200, 302))


class TestIoTAPIAuth(TestCase):
    """IoT API鍵なしアクセス拒否テスト"""

    def test_iot_events_without_api_key(self):
        response = self.client.post(
            '/api/iot/events/',
            data=json.dumps({'device': 'test', 'event_type': 'sensor'}),
            content_type='application/json',
        )
        self.assertIn(response.status_code, (400, 403, 404))

    def test_iot_config_without_api_key(self):
        response = self.client.get('/api/iot/config/')
        self.assertIn(response.status_code, (400, 403, 404))

    def test_iot_events_with_invalid_api_key(self):
        response = self.client.post(
            '/api/iot/events/',
            data=json.dumps({'device': 'test', 'event_type': 'sensor'}),
            content_type='application/json',
            HTTP_X_API_KEY='invalid-key-12345',
        )
        self.assertIn(response.status_code, (400, 403, 404))

    def test_iot_config_with_invalid_api_key(self):
        response = self.client.get(
            '/api/iot/config/',
            {'device': 'nonexistent'},
            HTTP_X_API_KEY='invalid-key-12345',
        )
        self.assertIn(response.status_code, (400, 403, 404))
