"""post_generator サービスのテスト"""
import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from booking.services.post_generator import (
    weighted_length,
    validate_tweet_length,
    truncate_to_fit,
    render_template,
    build_daily_staff_content,
    build_shift_publish_content,
    build_weekly_schedule_content,
    build_content,
)


class TestWeightedLength:
    def test_ascii_only(self):
        assert weighted_length('hello') == 5

    def test_japanese_chars(self):
        # 日本語は1文字=2
        assert weighted_length('こんにちは') == 10

    def test_mixed(self):
        # 'hello' = 5, 'こんにちは' = 10
        assert weighted_length('helloこんにちは') == 15

    def test_empty(self):
        assert weighted_length('') == 0

    def test_fullwidth_chars(self):
        # Fullwidth latin (FF00-FFEF)
        assert weighted_length('Ｈｅｌｌｏ') == 10


class TestValidateTweetLength:
    def test_valid_short(self):
        is_valid, wlen = validate_tweet_length('hello')
        assert is_valid is True
        assert wlen == 5

    def test_at_limit(self):
        # 280 ascii chars
        text = 'a' * 280
        is_valid, wlen = validate_tweet_length(text)
        assert is_valid is True
        assert wlen == 280

    def test_over_limit(self):
        text = 'a' * 281
        is_valid, wlen = validate_tweet_length(text)
        assert is_valid is False
        assert wlen == 281

    def test_japanese_limit(self):
        # 140 Japanese chars = 280 weighted
        text = 'あ' * 140
        is_valid, wlen = validate_tweet_length(text)
        assert is_valid is True
        assert wlen == 280

    def test_japanese_over_limit(self):
        text = 'あ' * 141
        is_valid, wlen = validate_tweet_length(text)
        assert is_valid is False


class TestTruncateToFit:
    def test_no_truncation_needed(self):
        text = 'hello'
        assert truncate_to_fit(text) == 'hello'

    def test_truncates_long_text(self):
        text = 'a' * 300
        result = truncate_to_fit(text)
        assert weighted_length(result) <= 280
        assert result.endswith('...')

    def test_truncates_japanese(self):
        text = 'あ' * 200  # 400 weighted
        result = truncate_to_fit(text)
        assert weighted_length(result) <= 280
        assert result.endswith('...')

    def test_custom_suffix(self):
        text = 'a' * 300
        result = truncate_to_fit(text, suffix='…')
        assert result.endswith('…')


class TestRenderTemplate:
    def test_basic_substitution(self):
        template = '{store_name}の本日のスタッフは{staff_list}です'
        context = {'store_name': 'テスト店', 'staff_list': '太郎、花子'}
        result = render_template(template, context)
        assert result == 'テスト店の本日のスタッフは太郎、花子です'

    def test_unknown_variable_preserved(self):
        template = '{store_name}は{unknown_var}です'
        context = {'store_name': 'テスト店'}
        result = render_template(template, context)
        assert result == 'テスト店は{unknown_var}です'

    def test_empty_context(self):
        template = '{store_name}'
        result = render_template(template, {})
        assert result == '{store_name}'

    def test_no_variables(self):
        template = '今日もよろしくお願いします！'
        result = render_template(template, {'store_name': 'test'})
        assert result == '今日もよろしくお願いします！'


@pytest.mark.django_db
class TestBuildDailyStaffContent:
    def test_with_assignments(self, store, shift_period, shift_assignment):
        from booking.models import PostTemplate
        template = PostTemplate.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            body_template='本日の{store_name}\n{date}\n出勤: {staff_list}',
        )
        content = build_daily_staff_content(
            store, shift_assignment.date, template,
        )
        assert store.name in content
        assert 'テストスタッフ' in content

    def test_no_assignments(self, store):
        from booking.models import PostTemplate
        template = PostTemplate.objects.create(
            store=store, platform='x', trigger_type='daily_staff',
            body_template='{store_name} 本日: {staff_list}',
        )
        content = build_daily_staff_content(store, date.today(), template)
        assert '未定' in content


@pytest.mark.django_db
class TestBuildContent:
    def test_manual_trigger(self, store):
        from booking.models import PostTemplate
        template = PostTemplate.objects.create(
            store=store, platform='x', trigger_type='manual',
            body_template='unused',
        )
        content = build_content(
            'manual', store, {'content': 'テスト手動投稿'}, template,
        )
        assert content == 'テスト手動投稿'

    def test_unknown_trigger(self, store):
        from booking.models import PostTemplate
        template = PostTemplate.objects.create(
            store=store, platform='x', trigger_type='manual',
            body_template='unused',
        )
        content = build_content('unknown_type', store, {}, template)
        assert content == ''
