"""予約投稿タスクのテスト"""
import pytest
from datetime import timedelta
from unittest.mock import patch

from django.utils import timezone

from booking.models import DraftPost, Store


@pytest.fixture
def scheduled_store(db):
    return Store.objects.create(
        name="予約投稿店舗", address="東京", business_hours="10-20", nearest_station="新宿",
    )


@pytest.mark.django_db
class TestScheduledPosts:
    def test_due_scheduled_post_gets_dispatched(self, scheduled_store):
        """期限到来した予約投稿が実行される"""
        past = timezone.now() - timedelta(minutes=5)
        draft = DraftPost.objects.create(
            store=scheduled_store,
            content=f'{scheduled_store.name} テスト予約投稿',
            platforms=['x'],
            status='scheduled',
            scheduled_at=past,
        )

        with patch('booking.services.post_dispatcher.dispatch_post') as mock_dispatch:
            from booking.tasks import task_check_scheduled_posts
            task_check_scheduled_posts()

            mock_dispatch.assert_called_once()
            draft.refresh_from_db()
            assert draft.status == 'posted'
            assert draft.posted_at is not None

    def test_future_scheduled_post_not_dispatched(self, scheduled_store):
        """未来の予約投稿は実行されない"""
        future = timezone.now() + timedelta(hours=2)
        draft = DraftPost.objects.create(
            store=scheduled_store,
            content='未来の投稿',
            platforms=['x'],
            status='scheduled',
            scheduled_at=future,
        )

        with patch('booking.services.post_dispatcher.dispatch_post') as mock_dispatch:
            from booking.tasks import task_check_scheduled_posts
            task_check_scheduled_posts()

            mock_dispatch.assert_not_called()
            draft.refresh_from_db()
            assert draft.status == 'scheduled'

    def test_non_scheduled_drafts_ignored(self, scheduled_store):
        """scheduled 以外のステータスは無視"""
        past = timezone.now() - timedelta(minutes=5)
        DraftPost.objects.create(
            store=scheduled_store,
            content='生成済みだけど予約ではない',
            platforms=['x'],
            status='generated',
            scheduled_at=past,
        )

        with patch('booking.services.post_dispatcher.dispatch_post') as mock_dispatch:
            from booking.tasks import task_check_scheduled_posts
            task_check_scheduled_posts()
            mock_dispatch.assert_not_called()

    @patch('booking.services.sns_draft_service._call_gemini_for_draft')
    def test_daily_draft_generation_task(self, mock_gemini, scheduled_store):
        """task_generate_daily_drafts が各店舗のドラフトを生成"""
        from booking.models import SocialAccount
        SocialAccount.objects.create(
            store=scheduled_store, platform='x',
            account_name='test', is_active=True,
        )
        mock_gemini.return_value = f'{scheduled_store.name} 本日の出勤！'

        with patch('booking.services.sns_evaluation_service._llm_judge_check', return_value=(0.8, 'OK')):
            from booking.tasks import task_generate_daily_drafts
            task_generate_daily_drafts()

        drafts = DraftPost.objects.filter(store=scheduled_store)
        assert drafts.count() >= 1

    def test_dispatch_failure_keeps_scheduled(self, scheduled_store):
        """投稿失敗時はステータスが scheduled のまま"""
        past = timezone.now() - timedelta(minutes=5)
        draft = DraftPost.objects.create(
            store=scheduled_store,
            content=f'{scheduled_store.name} 失敗テスト',
            platforms=['x'],
            status='scheduled',
            scheduled_at=past,
        )

        with patch('booking.services.post_dispatcher.dispatch_post', side_effect=Exception('API error')):
            from booking.tasks import task_check_scheduled_posts
            task_check_scheduled_posts()

            draft.refresh_from_db()
            # dispatch_post が例外を投げた場合、status は scheduled のまま
            assert draft.status == 'scheduled'
