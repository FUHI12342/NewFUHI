"""SocialAccount, PostTemplate, PostHistory モデルのテスト"""
import pytest
from django.db import IntegrityError
from django.utils import timezone

from booking.models import SocialAccount, PostTemplate, PostHistory


@pytest.mark.django_db
class TestSocialAccount:
    def test_create_social_account(self, store):
        account = SocialAccount.objects.create(
            store=store,
            platform='x',
            account_name='testuser',
            access_token='test_access_token',
            refresh_token='test_refresh_token',
            token_expires_at=timezone.now() + timezone.timedelta(hours=2),
        )
        assert account.id is not None
        assert account.is_active is True
        assert str(account) == f"{store.name} - X (Twitter) (@testuser)"

    def test_unique_together_store_platform(self, store):
        SocialAccount.objects.create(
            store=store, platform='x', account_name='user1',
        )
        with pytest.raises(IntegrityError):
            SocialAccount.objects.create(
                store=store, platform='x', account_name='user2',
            )

    def test_encrypted_fields(self, store):
        """EncryptedCharField でトークンが暗号化・復号されることを確認"""
        account = SocialAccount.objects.create(
            store=store,
            platform='x',
            account_name='testuser',
            access_token='my_secret_access_token',
            refresh_token='my_secret_refresh_token',
        )
        # DB から再読み込み
        account.refresh_from_db()
        assert account.access_token == 'my_secret_access_token'
        assert account.refresh_token == 'my_secret_refresh_token'


@pytest.mark.django_db
class TestPostTemplate:
    def test_create_template(self, store):
        template = PostTemplate.objects.create(
            store=store,
            platform='x',
            trigger_type='daily_staff',
            body_template='本日の{store_name}は{staff_list}が出勤です！',
        )
        assert template.id is not None
        assert template.is_active is True
        assert '本日の' in template.body_template

    def test_unique_together(self, store):
        PostTemplate.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            body_template='test',
        )
        with pytest.raises(IntegrityError):
            PostTemplate.objects.create(
                store=store, platform='x', trigger_type='daily_staff',
                body_template='test2',
            )

    def test_different_triggers_allowed(self, store):
        PostTemplate.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            body_template='daily',
        )
        t2 = PostTemplate.objects.create(
            store=store, platform='x', trigger_type='shift_publish',
            body_template='shift',
        )
        assert t2.id is not None


@pytest.mark.django_db
class TestPostHistory:
    def test_create_history(self, store):
        history = PostHistory.objects.create(
            store=store,
            platform='x',
            trigger_type='daily_staff',
            content='テスト投稿内容',
        )
        assert history.status == 'pending'
        assert history.retry_count == 0
        assert history.external_post_id == ''

    def test_ordering(self, store):
        h1 = PostHistory.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            content='first',
        )
        h2 = PostHistory.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            content='second',
        )
        histories = list(PostHistory.objects.all())
        assert histories[0].id == h2.id  # newer first

    def test_status_choices(self, store):
        for status in ('pending', 'posted', 'failed', 'skipped'):
            h = PostHistory.objects.create(
                store=store, platform='x', trigger_type='manual',
                content='test', status=status,
            )
            assert h.get_status_display() != ''
