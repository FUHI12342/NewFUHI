"""AI 下書き生成 + LLM Judge 評価のテスト (Gemini mock)"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date

from booking.models import DraftPost, KnowledgeEntry
from booking.services.sns_draft_service import generate_daily_draft
from booking.services.sns_evaluation_service import (
    evaluate_draft_quality, _rule_based_check, BANNED_WORDS,
)


@pytest.mark.django_db
class TestGenerateDailyDraft:
    @patch('booking.services.sns_draft_service._call_gemini_for_draft')
    def test_generates_draft(self, mock_gemini, store):
        mock_gemini.return_value = f'今日は{store.name}で素敵な占い師がお待ちしています！🔮✨'
        draft = generate_daily_draft(store)
        assert draft is not None
        assert draft.status == 'generated'
        assert store.name in draft.content
        assert draft.platforms == ['x']

    @patch('booking.services.sns_draft_service._call_gemini_for_draft')
    def test_generates_with_custom_platforms(self, mock_gemini, store):
        mock_gemini.return_value = 'テスト投稿'
        draft = generate_daily_draft(store, platforms=['x', 'instagram'])
        assert draft.platforms == ['x', 'instagram']

    @patch('booking.services.sns_draft_service._call_gemini_for_draft')
    def test_returns_none_on_api_failure(self, mock_gemini, store):
        mock_gemini.return_value = None
        draft = generate_daily_draft(store)
        assert draft is None

    @patch('booking.services.sns_draft_service._call_gemini_for_draft')
    def test_stores_ai_generated_content(self, mock_gemini, store):
        mock_gemini.return_value = 'AI生成テキスト'
        draft = generate_daily_draft(store)
        assert draft.ai_generated_content == 'AI生成テキスト'
        assert draft.content == 'AI生成テキスト'


@pytest.mark.django_db
class TestRuleBasedCheck:
    def test_empty_content(self, store):
        draft = DraftPost(store=store, content='', platforms=['x'])
        issues, deduction = _rule_based_check(draft)
        assert any('空' in i for i in issues)
        assert deduction >= 1.0

    def test_banned_words(self, store):
        draft = DraftPost(store=store, content=f'{store.name} テスト {BANNED_WORDS[0]}', platforms=['x'])
        issues, deduction = _rule_based_check(draft)
        assert any('禁止ワード' in i for i in issues)

    def test_missing_store_name(self, store):
        draft = DraftPost(store=store, content='今日も素敵な日', platforms=['x'])
        issues, deduction = _rule_based_check(draft)
        assert any('店舗名' in i for i in issues)

    def test_valid_content_no_issues(self, store):
        draft = DraftPost(store=store, content=f'{store.name} 本日もお待ちしています！', platforms=['x'])
        issues, deduction = _rule_based_check(draft)
        assert deduction == 0.0


@pytest.mark.django_db
class TestEvaluateDraftQuality:
    @patch('booking.services.sns_evaluation_service._llm_judge_check')
    def test_evaluation_saves_score(self, mock_judge, store):
        mock_judge.return_value = (0.85, 'Good quality post')
        draft = DraftPost.objects.create(
            store=store, content=f'{store.name} 本日もお待ちしています！',
            platforms=['x'], status='generated',
        )
        score, feedback = evaluate_draft_quality(draft)
        draft.refresh_from_db()
        assert draft.quality_score is not None
        assert draft.quality_score > 0
        assert draft.quality_feedback != ''

    @patch('booking.services.sns_evaluation_service._llm_judge_check')
    def test_fallback_to_rule_only(self, mock_judge, store):
        mock_judge.return_value = (None, '')
        draft = DraftPost.objects.create(
            store=store, content=f'{store.name} テスト投稿',
            platforms=['x'], status='generated',
        )
        score, feedback = evaluate_draft_quality(draft)
        assert score >= 0.0
        assert score <= 1.0
