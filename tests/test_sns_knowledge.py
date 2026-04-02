"""SNS ナレッジサービスのテスト"""
import pytest
from datetime import date

from booking.models import KnowledgeEntry, Store, Staff
from booking.models.shifts import ShiftPeriod, ShiftAssignment
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

    def test_includes_store_address(self, store):
        context = build_knowledge_context(store)
        if store.address:
            assert store.address in context

    def test_includes_shift_assignments(self, store, staff, shift_period, shift_assignment):
        target = shift_assignment.date
        context = build_knowledge_context(store, target_date=target)
        assert staff.name in context
        assert '出勤キャスト' in context

    def test_no_shifts_shows_unregistered(self, store):
        target = date(2099, 12, 31)  # 未来日でシフトなし
        context = build_knowledge_context(store, target_date=target)
        assert '未登録' in context

    def test_staff_introduction_in_context(self, store, shift_period, shift_assignment):
        staff = shift_assignment.staff
        staff.introduction = 'タロット歴10年のベテランです'
        staff.save()
        target = shift_assignment.date
        context = build_knowledge_context(store, target_date=target)
        assert 'タロット歴10年' in context

    def test_default_target_date_is_today(self, store):
        """target_date=None の場合、今日の日付が使われる"""
        context = build_knowledge_context(store)
        from django.utils import timezone
        today = timezone.localdate()
        assert today.strftime('%Y/%m/%d') in context
