"""Tests for AdminChatService and GuideChatService AI chat services."""
import json
import pytest
from unittest.mock import patch, MagicMock

from booking.services.ai_chat import (
    AdminChatService, GuideChatService, _load_knowledge, _call_gemini,
    _knowledge_cache,
)


class TestAdminChatService:
    """Tests for AdminChatService."""

    @pytest.mark.django_db
    def test_get_response_returns_string(self, mock_gemini_api):
        """AdminChatService.get_response returns a string."""
        service = AdminChatService()
        result = service.get_response('how to manage bookings')
        assert isinstance(result, str)
        assert result == 'テスト回答'

    @pytest.mark.django_db
    def test_get_response_calls_gemini(self, mock_gemini_api):
        """AdminChatService.get_response calls _call_gemini."""
        service = AdminChatService()
        service.get_response('test question')
        mock_gemini_api.assert_called_once()

    @pytest.mark.django_db
    def test_get_response_with_history(self, mock_gemini_api):
        """AdminChatService passes conversation_history to _call_gemini."""
        service = AdminChatService()
        history = [{'role': 'user', 'content': 'hi'}, {'role': 'model', 'content': 'hello'}]
        service.get_response('follow-up', conversation_history=history)
        call_args = mock_gemini_api.call_args
        assert call_args[0][3] == history


class TestGuideChatService:
    """Tests for GuideChatService."""

    @pytest.mark.django_db
    def test_get_response_returns_string(self, mock_gemini_api):
        """GuideChatService.get_response returns a string."""
        service = GuideChatService()
        result = service.get_response('how to book')
        assert isinstance(result, str)

    @pytest.mark.django_db
    def test_get_response_calls_gemini(self, mock_gemini_api):
        """GuideChatService.get_response calls _call_gemini."""
        service = GuideChatService()
        service.get_response('booking question')
        mock_gemini_api.assert_called_once()


class TestLoadKnowledge:
    """Tests for _load_knowledge function."""

    def test_caches_file_content(self, tmp_path):
        """_load_knowledge caches file content after first read."""
        # Clear cache
        _knowledge_cache.clear()
        test_file = tmp_path / 'test_knowledge.txt'
        test_file.write_text('Knowledge content here')

        with patch('booking.services.ai_chat.settings') as mock_settings:
            mock_settings.BASE_DIR = str(tmp_path)
            result1 = _load_knowledge('test_knowledge.txt')
            result2 = _load_knowledge('test_knowledge.txt')
            assert result1 == 'Knowledge content here'
            assert result2 == 'Knowledge content here'
            # Should be cached
            assert 'test_knowledge.txt' in _knowledge_cache

        # Clean up
        _knowledge_cache.clear()

    def test_returns_empty_for_missing_file(self):
        """_load_knowledge returns empty string for non-existent file."""
        _knowledge_cache.clear()
        with patch('booking.services.ai_chat.settings') as mock_settings:
            mock_settings.BASE_DIR = '/nonexistent'
            result = _load_knowledge('does_not_exist.txt')
            assert result == ''
        _knowledge_cache.clear()


class TestCallGemini:
    """Tests for _call_gemini function."""

    def test_handles_missing_api_key(self, settings):
        """_call_gemini returns error message when GEMINI_API_KEY is not set."""
        settings.GEMINI_API_KEY = ''
        result = _call_gemini('system', 'knowledge', 'question')
        assert 'API キーが設定されていません' in result

    def test_handles_http_403(self, settings):
        """_call_gemini returns auth error message on HTTP 403."""
        settings.GEMINI_API_KEY = 'test-key'
        import urllib.error
        error = urllib.error.HTTPError(
            url='https://api.example.com',
            code=403,
            msg='Forbidden',
            hdrs={},
            fp=None,
        )
        with patch('urllib.request.urlopen', side_effect=error):
            result = _call_gemini('system', 'knowledge', 'question')
            assert 'API キーを確認' in result

    def test_handles_http_429_retry(self, settings):
        """_call_gemini retries on HTTP 429 (rate limit)."""
        settings.GEMINI_API_KEY = 'test-key'
        import urllib.error
        error = urllib.error.HTTPError(
            url='https://api.example.com',
            code=429,
            msg='Too Many Requests',
            hdrs={},
            fp=None,
        )
        with patch('urllib.request.urlopen', side_effect=error):
            with patch('time.sleep'):  # Speed up test
                result = _call_gemini('system', 'knowledge', 'question')
                # After retries exhausted, returns error message
                assert 'エラーが発生しました' in result
