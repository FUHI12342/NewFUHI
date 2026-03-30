"""SNS 下書き管理ビューのテスト"""
import pytest
from django.contrib.auth.models import User
from django.test import Client
from datetime import date

from booking.models import DraftPost, Store


@pytest.fixture
def admin_client(db):
    user = User.objects.create_superuser('admin', 'admin@test.com', 'testpass')
    client = Client()
    client.login(username='admin', password='testpass')
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


@pytest.mark.django_db
class TestDraftListView:
    def test_list_view_accessible(self, admin_client):
        response = admin_client.get('/admin/social/drafts/')
        assert response.status_code == 200

    def test_list_shows_drafts(self, admin_client, sample_draft):
        response = admin_client.get('/admin/social/drafts/')
        assert sample_draft.content.encode() in response.content

    def test_filter_by_status(self, admin_client, sample_draft):
        response = admin_client.get('/admin/social/drafts/?status=generated')
        assert response.status_code == 200


@pytest.mark.django_db
class TestDraftEditView:
    def test_edit_updates_content(self, admin_client, sample_draft):
        response = admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/edit/',
            {'content': '更新された内容'},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.content == '更新された内容'
        assert sample_draft.status == 'reviewed'


@pytest.mark.django_db
class TestDraftGenerateView:
    def test_generate_form_accessible(self, admin_client):
        response = admin_client.get('/admin/social/drafts/generate/')
        assert response.status_code == 200


@pytest.mark.django_db
class TestDraftScheduleView:
    def test_schedule_sets_datetime(self, admin_client, sample_draft):
        response = admin_client.post(
            f'/admin/social/drafts/{sample_draft.pk}/schedule/',
            {'scheduled_at': '2026-04-01T10:00:00'},
        )
        assert response.status_code == 302
        sample_draft.refresh_from_db()
        assert sample_draft.status == 'scheduled'
        assert sample_draft.scheduled_at is not None
