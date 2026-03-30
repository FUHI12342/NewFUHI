"""x_posting_service のテスト (X API はモック)"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from django.utils import timezone

from booking.services.x_posting_service import (
    post_tweet,
    refresh_x_token,
    validate_x_credentials,
    PostResult,
    RateLimitError,
    TokenExpiredError,
    RetryableError,
    XApiError,
)


@pytest.fixture(autouse=True)
def x_api_settings(settings):
    """テスト用X API設定"""
    settings.X_CLIENT_ID = 'test_client_id'
    settings.X_CLIENT_SECRET = 'test_client_secret'
    settings.X_REDIRECT_URI = 'http://localhost/callback'
    settings.CELERY_BROKER_URL = 'redis://localhost:6379/0'


@pytest.fixture
def social_account(store):
    from booking.models import SocialAccount
    return SocialAccount.objects.create(
        store=store,
        platform='x',
        account_name='testuser',
        access_token='valid_access_token',
        refresh_token='valid_refresh_token',
        token_expires_at=timezone.now() + timedelta(hours=2),
    )


@pytest.fixture
def expired_account(store):
    from booking.models import SocialAccount
    return SocialAccount.objects.create(
        store=store,
        platform='x',
        account_name='expired_user',
        access_token='expired_token',
        refresh_token='valid_refresh',
        token_expires_at=timezone.now() - timedelta(hours=1),
    )


@pytest.fixture
def mock_redis():
    with patch('booking.services.x_posting_service._get_redis') as mock:
        redis_mock = MagicMock()
        redis_mock.set.return_value = True  # Lock acquired
        mock.return_value = redis_mock
        yield redis_mock


@pytest.mark.django_db
class TestPostTweet:
    @patch('booking.services.x_posting_service.requests.post')
    def test_successful_post(self, mock_post, social_account):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {'data': {'id': '12345'}}
        mock_resp.headers = {
            'x-rate-limit-remaining': '15',
            'x-rate-limit-reset': '1700000000',
        }
        mock_post.return_value = mock_resp

        result = post_tweet(social_account, 'テストツイート')
        assert result.success is True
        assert result.external_post_id == '12345'
        assert result.rate_limit_remaining == 15

    @patch('booking.services.x_posting_service.requests.post')
    def test_rate_limit_429(self, mock_post, social_account):
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.headers = {
            'x-rate-limit-remaining': '0',
            'x-rate-limit-reset': '1700000000',
        }
        mock_post.return_value = mock_resp

        with pytest.raises(RateLimitError) as exc_info:
            post_tweet(social_account, 'テスト')
        assert exc_info.value.reset_at == 1700000000

    @patch('booking.services.x_posting_service.requests.post')
    def test_server_error_5xx(self, mock_post, social_account):
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.headers = {}
        mock_post.return_value = mock_resp

        with pytest.raises(RetryableError):
            post_tweet(social_account, 'テスト')

    @patch('booking.services.x_posting_service.requests.post')
    def test_401_triggers_refresh_and_retry(
        self, mock_post, social_account, mock_redis,
    ):
        """401 → トークンリフレッシュ → リトライ成功"""
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.headers = {}

        resp_refresh = MagicMock()
        resp_refresh.status_code = 200
        resp_refresh.json.return_value = {
            'access_token': 'new_access',
            'refresh_token': 'new_refresh',
            'expires_in': 7200,
        }

        resp_201 = MagicMock()
        resp_201.status_code = 201
        resp_201.json.return_value = {'data': {'id': '99999'}}
        resp_201.headers = {}

        mock_post.side_effect = [resp_401, resp_refresh, resp_201]

        result = post_tweet(social_account, 'テスト')
        assert result.success is True
        assert result.external_post_id == '99999'

    @patch('booking.services.x_posting_service.requests.post')
    def test_timeout_raises_retryable(self, mock_post, social_account):
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("timeout")

        with pytest.raises(RetryableError):
            post_tweet(social_account, 'テスト')


@pytest.mark.django_db
class TestRefreshXToken:
    @patch('booking.services.x_posting_service.requests.post')
    def test_successful_refresh(self, mock_post, expired_account, mock_redis):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'expires_in': 7200,
        }
        mock_post.return_value = mock_resp

        refresh_x_token(expired_account)
        expired_account.refresh_from_db()

        assert expired_account.access_token == 'new_access_token'
        assert expired_account.refresh_token == 'new_refresh_token'
        assert expired_account.token_expires_at > timezone.now()

    @patch('booking.services.x_posting_service.requests.post')
    def test_refresh_failure(self, mock_post, expired_account, mock_redis):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = 'Bad Request'
        mock_post.return_value = mock_resp

        with pytest.raises(XApiError):
            refresh_x_token(expired_account)

    def test_lock_contention(self, expired_account, mock_redis):
        """他のワーカーがリフレッシュ中 → ロック取得失敗"""
        mock_redis.set.return_value = False  # Lock not acquired

        # 他のワーカーがリフレッシュ成功をシミュレート
        expired_account.token_expires_at = timezone.now() + timedelta(hours=2)
        expired_account.save()

        with patch('booking.services.x_posting_service.time.sleep'):
            refresh_x_token(expired_account)


@pytest.mark.django_db
class TestValidateXCredentials:
    @patch('booking.services.x_posting_service.requests.get')
    def test_valid_credentials(self, mock_get, social_account):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        assert validate_x_credentials(social_account) is True

    @patch('booking.services.x_posting_service.requests.get')
    def test_invalid_credentials(self, mock_get, social_account):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        assert validate_x_credentials(social_account) is False
