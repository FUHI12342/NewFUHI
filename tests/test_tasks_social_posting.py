"""SNS自動投稿 Celery タスクのテスト"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

from django.utils import timezone

from booking.models import SocialAccount, PostTemplate, ShiftPeriod


@pytest.mark.django_db
class TestTaskPostShiftPublished:
    @patch('booking.tasks.task_post_to_x.apply_async')
    def test_queues_x_api_task(self, mock_apply, store, shift_period):
        from booking.tasks import task_post_shift_published

        task_post_shift_published(shift_period.id)

        mock_apply.assert_called_once()
        _, kwargs = mock_apply.call_args
        assert kwargs['queue'] == 'x_api'
        call_args = kwargs.get('args', mock_apply.call_args[0][0] if mock_apply.call_args[0] else None)
        assert call_args[0] == store.id  # store_id
        assert call_args[1] == 'shift_publish'

    def test_nonexistent_period(self):
        from booking.tasks import task_post_shift_published
        # Should not raise, just log
        task_post_shift_published(99999)


@pytest.mark.django_db
class TestTaskPostDailyStaff:
    @patch('booking.tasks.task_post_to_x.apply_async')
    def test_dispatches_for_each_active_account(self, mock_apply, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
            token_expires_at=timezone.now() + timedelta(hours=2),
        )
        from booking.tasks import task_post_daily_staff
        task_post_daily_staff()

        assert mock_apply.call_count == 1
        kwargs = mock_apply.call_args[1]
        call_args = kwargs.get('args', mock_apply.call_args[0][0] if mock_apply.call_args[0] else None)
        assert call_args[1] == 'daily_staff'

    @patch('booking.tasks.task_post_to_x.apply_async')
    def test_skips_inactive_accounts(self, mock_apply, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='inactive',
            is_active=False,
        )
        from booking.tasks import task_post_daily_staff
        task_post_daily_staff()

        mock_apply.assert_not_called()


@pytest.mark.django_db
class TestTaskPostWeeklySchedule:
    @patch('booking.tasks.task_post_to_x.apply_async')
    def test_dispatches_weekly(self, mock_apply, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
            token_expires_at=timezone.now() + timedelta(hours=2),
        )
        from booking.tasks import task_post_weekly_schedule
        task_post_weekly_schedule()

        assert mock_apply.call_count == 1
        kwargs = mock_apply.call_args[1]
        call_args = kwargs.get('args', mock_apply.call_args[0][0] if mock_apply.call_args[0] else None)
        assert call_args[1] == 'weekly_schedule'


@pytest.mark.django_db
class TestTaskRefreshSocialTokens:
    @patch('booking.services.x_posting_service.refresh_x_token')
    def test_refreshes_expiring_tokens(self, mock_refresh, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
            token_expires_at=timezone.now() + timedelta(hours=3),
        )
        from booking.tasks import task_refresh_social_tokens
        task_refresh_social_tokens()

        mock_refresh.assert_called_once()

    @patch('booking.services.x_posting_service.refresh_x_token')
    def test_skips_valid_tokens(self, mock_refresh, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
            token_expires_at=timezone.now() + timedelta(days=30),
        )
        from booking.tasks import task_refresh_social_tokens
        task_refresh_social_tokens()

        mock_refresh.assert_not_called()

    @patch('booking.services.x_posting_service.refresh_x_token')
    def test_handles_refresh_failure(self, mock_refresh, store):
        mock_refresh.side_effect = Exception("refresh failed")
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
            token_expires_at=timezone.now() + timedelta(hours=1),
        )
        from booking.tasks import task_refresh_social_tokens
        # Should not raise
        task_refresh_social_tokens()


@pytest.mark.django_db
class TestTaskPostToX:
    @patch('booking.services.post_dispatcher.dispatch_post')
    def test_calls_dispatch_post(self, mock_dispatch, store):
        from booking.tasks import task_post_to_x
        task_post_to_x(store.id, 'daily_staff', '{}')
        mock_dispatch.assert_called_once_with(store.id, 'daily_staff', '{}')
