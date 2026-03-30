"""post_dispatcher サービスのテスト"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta

from django.utils import timezone

from booking.models import SocialAccount, PostTemplate, PostHistory
from booking.services.post_dispatcher import dispatch_post, retry_failed_post
from booking.services.x_posting_service import (
    PostResult,
    RateLimitError,
    XApiError,
)


@pytest.fixture
def social_account(store):
    return SocialAccount.objects.create(
        store=store,
        platform='x',
        account_name='testuser',
        access_token='token',
        refresh_token='refresh',
        token_expires_at=timezone.now() + timedelta(hours=2),
    )


@pytest.fixture
def post_template(store):
    return PostTemplate.objects.create(
        store=store,
        platform='x',
        trigger_type='daily_staff',
        body_template='{store_name} 本日のスタッフ: {staff_list}',
    )


@pytest.mark.django_db
class TestDispatchPost:
    @patch('booking.services.post_dispatcher.can_post', return_value=(True, 'ok'))
    @patch('booking.services.post_dispatcher.record_post')
    @patch('booking.services.post_dispatcher.post_tweet')
    def test_successful_dispatch(
        self, mock_tweet, mock_record, mock_can_post,
        store, social_account, post_template,
    ):
        mock_tweet.return_value = PostResult(
            success=True, external_post_id='12345',
        )

        dispatch_post(store.id, 'daily_staff', {})

        history = PostHistory.objects.filter(store=store).first()
        assert history is not None
        assert history.status == 'posted'
        assert history.external_post_id == '12345'
        mock_record.assert_called_once_with(store.id)

    @patch('booking.services.post_dispatcher.can_post', return_value=(False, 'daily_app_limit'))
    def test_rate_limited_skipped(
        self, mock_can_post,
        store, social_account, post_template,
    ):
        dispatch_post(store.id, 'daily_staff', {})

        history = PostHistory.objects.filter(store=store).first()
        assert history is not None
        assert history.status == 'skipped'
        assert 'daily_app_limit' in history.error_message

    def test_no_social_account(self, store, post_template):
        """SocialAccount がない場合はスキップ"""
        dispatch_post(store.id, 'daily_staff', {})
        assert PostHistory.objects.count() == 0

    def test_no_template(self, store, social_account):
        """PostTemplate がない場合はスキップ"""
        dispatch_post(store.id, 'daily_staff', {})
        assert PostHistory.objects.count() == 0

    @patch('booking.services.post_dispatcher.can_post', return_value=(True, 'ok'))
    @patch('booking.services.post_dispatcher.post_tweet')
    def test_api_error_records_failure(
        self, mock_tweet, mock_can_post,
        store, social_account, post_template,
    ):
        mock_tweet.side_effect = XApiError("API error")

        dispatch_post(store.id, 'daily_staff', {})

        history = PostHistory.objects.filter(store=store).first()
        assert history.status == 'failed'
        assert 'API error' in history.error_message
        assert history.retry_count == 1

    @patch('booking.services.post_dispatcher.can_post', return_value=(True, 'ok'))
    @patch('booking.services.post_dispatcher.post_tweet')
    def test_rate_limit_error_records_skipped(
        self, mock_tweet, mock_can_post,
        store, social_account, post_template,
    ):
        mock_tweet.side_effect = RateLimitError(reset_at=1700000000)

        dispatch_post(store.id, 'daily_staff', {})

        history = PostHistory.objects.filter(store=store).first()
        assert history.status == 'skipped'

    def test_nonexistent_store(self):
        """存在しないstoreではスキップ"""
        dispatch_post(99999, 'daily_staff', {})
        assert PostHistory.objects.count() == 0

    @patch('booking.services.post_dispatcher.can_post', return_value=(True, 'ok'))
    @patch('booking.services.post_dispatcher.record_post')
    @patch('booking.services.post_dispatcher.post_tweet')
    def test_json_string_context(
        self, mock_tweet, mock_record, mock_can_post,
        store, social_account, post_template,
    ):
        """context_data が JSON 文字列でも動作する"""
        mock_tweet.return_value = PostResult(success=True, external_post_id='777')
        dispatch_post(store.id, 'daily_staff', '{}')

        history = PostHistory.objects.filter(store=store).first()
        assert history.status == 'posted'


@pytest.mark.django_db
class TestRetryFailedPost:
    @patch('booking.services.post_dispatcher.can_post', return_value=(True, 'ok'))
    @patch('booking.services.post_dispatcher.record_post')
    @patch('booking.services.post_dispatcher.post_tweet')
    def test_retry_success(
        self, mock_tweet, mock_record, mock_can_post,
        store, social_account,
    ):
        history = PostHistory.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            content='retry test', status='failed', retry_count=1,
        )
        mock_tweet.return_value = PostResult(
            success=True, external_post_id='retry123',
        )

        retry_failed_post(history.id)
        history.refresh_from_db()
        assert history.status == 'posted'

    def test_retry_max_exceeded(self, store, social_account):
        history = PostHistory.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            content='retry test', status='failed', retry_count=2,
        )
        retry_failed_post(history.id)
        history.refresh_from_db()
        assert history.status == 'failed'  # unchanged

    def test_retry_non_failed_skipped(self, store):
        history = PostHistory.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            content='test', status='posted',
        )
        retry_failed_post(history.id)
        history.refresh_from_db()
        assert history.status == 'posted'  # unchanged
