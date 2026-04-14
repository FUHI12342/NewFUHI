"""SNS 下書き管理ビューのテスト"""
import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.test import Client
from datetime import date

from booking.models import DraftPost, Store


@pytest.fixture
def draft_admin_user(db):
    return User.objects.create_superuser('admin', 'admin@test.com', 'testpass')


@pytest.fixture
def draft_admin_client(db, draft_admin_user):
    client = Client()
    client.login(username='admin', password='testpass')
    return client


@pytest.fixture
def anon_client(db):
    return Client()


@pytest.fixture
def staff_only_client(db):
    user = User.objects.create_user('staffonly', 'staff@test.com', 'testpass')
    client = Client()
    client.login(username='staffonly', password='testpass')
    return client


@pytest.fixture
def draft_store(db):
    return Store.objects.create(
        name="ドラフト店舗", address="東京", business_hours="10-20", nearest_station="渋谷",
    )


@pytest.fixture
def sample_draft(db, draft_store):
    return DraftPost.objects.create(
        store=draft_store,
        content="テスト投稿内容です！",
        ai_generated_content="テスト投稿内容です！",
        platforms=["x"],
        status="generated",
        target_date=date.today(),
    )


@pytest.fixture
def posted_draft(db, draft_store):
    return DraftPost.objects.create(
        store=draft_store,
        content="投稿済み内容",
        ai_generated_content="投稿済み内容",
        platforms=["x"],
        status="posted",
        target_date=date.today(),
    )


# ==============================
# StaffRequiredMixin (権限チェック)
# ==============================

@pytest.mark.django_db
class TestStaffRequiredMixin:
    def test_anonymous_redirected(self, anon_client):
        response = anon_client.get('/admin/social/drafts/')
        assert response.status_code == 302

    def test_non_staff_user_denied(self, staff_only_client):
        response = staff_only_client.get('/admin/social/drafts/')
        # LoginRequiredMixin redirects or returns 403
        assert response.status_code in (302, 403)


# ==============================
# DraftListView
# ==============================

@pytest.mark.django_db
class TestDraftListView:
    def test_list_view_accessible(self, draft_admin_client):
        response = draft_admin_client.get('/admin/social/drafts/')
        assert response.status_code == 200

    def test_list_shows_drafts(self, draft_admin_client, sample_draft):
        response = draft_admin_client.get('/admin/social/drafts/')
        assert sample_draft.content.encode() in response.content

    def test_filter_by_status(self, draft_admin_client, sample_draft):
        response = draft_admin_client.get('/admin/social/drafts/?status=generated')
        assert response.status_code == 200

    def test_filter_by_store(self, draft_admin_client, sample_draft, draft_store):
        response = draft_admin_client.get(f'/admin/social/drafts/?store={draft_store.pk}')
        assert response.status_code == 200

    def test_list_context_has_stores(self, draft_admin_client, draft_store):
        response = draft_admin_client.get('/admin/social/drafts/')
        assert 'stores' in response.context
        assert 'status_choices' in response.context


# ==============================
# DraftEditView
# ==============================

@pytest.mark.django_db
class TestDraftEditView:
    def test_edit_updates_content(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/edit/',
            {'content': '更新された内容'},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.content == '更新された内容'
        assert sample_draft.status == 'reviewed'

    def test_edit_empty_content_rejected(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/edit/',
            {'content': ''},
        )
        assert response.status_code == 400

    def test_edit_updates_platforms(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/edit/',
            {'content': '更新内容', 'platforms': ['x', 'instagram']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert 'instagram' in sample_draft.platforms


# ==============================
# DraftPostView (API / ブラウザ投稿)
# ==============================

@pytest.mark.django_db
class TestDraftPostView:
    @patch('booking.views_social_drafts.DraftPostView._dispatch')
    def test_api_post_success(self, mock_dispatch, draft_admin_client, sample_draft):
        mock_dispatch.return_value = (True, '投稿完了')
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/post/',
            {'platforms': ['x']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'posted'
        assert sample_draft.posted_at is not None

    @patch('booking.views_social_drafts.DraftPostView._dispatch')
    def test_api_post_failure(self, mock_dispatch, draft_admin_client, sample_draft):
        mock_dispatch.return_value = (False, 'エラー発生')
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/post/',
            {'platforms': ['x']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'generated'  # 失敗時は変わらない

    @patch('booking.views_social_drafts.DraftPostView._dispatch')
    def test_browser_post_success(self, mock_dispatch, draft_admin_client, sample_draft):
        mock_dispatch.return_value = (True, 'ブラウザ投稿完了')
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/post/',
            {'platforms': ['x']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'posted'

    @patch('booking.views_social_drafts.DraftPostView._dispatch')
    def test_post_uses_draft_platforms_when_none_sent(self, mock_dispatch, draft_admin_client, sample_draft):
        mock_dispatch.return_value = (True, 'OK')
        # プラットフォームを送らない場合、ドラフトの platforms が使用される
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/post/',
            {},
        )
        assert response.status_code == 302
        mock_dispatch.assert_called_once()

    @patch('booking.views_social_drafts.DraftPostView._dispatch')
    def test_post_exception_handled(self, mock_dispatch, draft_admin_client, sample_draft):
        mock_dispatch.side_effect = Exception('Network error')
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/post/',
            {'platforms': ['x']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'generated'


# ==============================
# DraftGenerateView
# ==============================

@pytest.mark.django_db
class TestDraftGenerateView:
    def test_generate_form_accessible(self, draft_admin_client):
        response = draft_admin_client.get('/admin/social/drafts/generate/')
        assert response.status_code == 200

    @patch('booking.services.sns_evaluation_service.evaluate_draft_quality')
    @patch('booking.services.sns_draft_service.generate_daily_draft')
    def test_generate_post_creates_draft(self, mock_gen, mock_eval, draft_admin_client, draft_store):
        mock_draft = MagicMock()
        mock_draft.quality_score = 0.85
        mock_gen.return_value = mock_draft
        mock_eval.return_value = (0.85, 'Good')
        response = draft_admin_client.post(
            '/admin/social/drafts/generate/',
            {'store_id': draft_store.pk, 'platforms': ['x']},
        )
        assert response.status_code == 302
        mock_gen.assert_called_once()

    @patch('booking.services.sns_draft_service.generate_daily_draft')
    def test_generate_post_failure(self, mock_gen, draft_admin_client, draft_store):
        mock_gen.return_value = None
        response = draft_admin_client.post(
            '/admin/social/drafts/generate/',
            {'store_id': draft_store.pk, 'platforms': ['x']},
        )
        assert response.status_code == 302


# ==============================
# DraftRegenerateView
# ==============================

@pytest.mark.django_db
class TestDraftRegenerateView:
    @patch('booking.services.sns_evaluation_service.evaluate_draft_quality')
    @patch('booking.services.sns_draft_service.generate_daily_draft')
    def test_regenerate_creates_new_draft(self, mock_gen, mock_eval, draft_admin_client, sample_draft):
        new_mock = MagicMock()
        new_mock.quality_score = 0.90
        mock_gen.return_value = new_mock
        mock_eval.return_value = (0.90, 'Excellent')
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/regenerate/',
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'rejected'

    @patch('booking.services.sns_draft_service.generate_daily_draft')
    def test_regenerate_failure_keeps_original(self, mock_gen, draft_admin_client, sample_draft):
        mock_gen.return_value = None
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/regenerate/',
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'generated'  # 変わらない


# ==============================
# DraftScheduleView
# ==============================

@pytest.mark.django_db
class TestDraftScheduleView:
    def test_schedule_sets_datetime(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/schedule/',
            {'scheduled_at': '2026-04-01T10:00:00'},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'scheduled'
        assert sample_draft.scheduled_at is not None

    def test_schedule_missing_datetime_returns_400(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/schedule/',
            {},
        )
        assert response.status_code == 400

    def test_schedule_invalid_datetime_returns_400(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/schedule/',
            {'scheduled_at': 'not-a-date'},
        )
        assert response.status_code == 400

    def test_schedule_updates_platforms(self, draft_admin_client, sample_draft):
        response = draft_admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/schedule/',
            {'scheduled_at': '2026-04-01T10:00:00', 'platforms': ['instagram']},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert 'instagram' in sample_draft.platforms
