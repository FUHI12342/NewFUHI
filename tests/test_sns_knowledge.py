"""SNS ナレッジサービスのテスト"""
import pytest
from datetime import date

from booking.models import KnowledgeEntry, Store, Staff
from booking.services.sns_knowledge_service import build_knowledge_context


@pytest.mark.django_db
class TestKnowledgeEntry:
    def test_create_knowledge_entry(self, store):
        entry = KnowledgeEntry.objects.create(
            store=store,
            category='store_info',
            title='テスト情報',
            content='テスト店舗の紹介です。',
        )
        assert entry.id is not None
        assert entry.is_active is True
        assert 'テスト情報' in str(entry)

    def test_cast_profile_with_staff(self, store, staff):
        entry = KnowledgeEntry.objects.create(
            store=store,
            category='cast_profile',
            staff=staff,
            title=f'{staff.name}プロフィール',
            content=f'{staff.name}は凄い占い師です。',
        )
        assert entry.staff == staff
        assert entry.category == 'cast_profile'


@pytest.mark.django_db
class TestBuildKnowledgeContext:
    def test_includes_store_info(self, store):
        context = build_knowledge_context(store)
        assert store.name in context
        assert '店舗情報' in context

    def test_includes_knowledge_entries(self, store):
        KnowledgeEntry.objects.create(
            store=store, category='campaign',
            title='春キャンペーン', content='全品20%OFF！',
        )
        context = build_knowledge_context(store)
        assert '春キャンペーン' in context
        assert '全品20%OFF' in context

    def test_excludes_inactive_entries(self, store):
        KnowledgeEntry.objects.create(
            store=store, category='custom',
            title='古い情報', content='もう使わない', is_active=False,
        )
        context = build_knowledge_context(store)
        assert '古い情報' not in context
