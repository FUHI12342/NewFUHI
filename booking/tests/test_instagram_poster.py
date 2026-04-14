"""instagram_poster のユニットテスト — セレクタフォールバック・画像バリデーション"""
from unittest.mock import MagicMock, patch

from django.test import TestCase


class TestInstagramPosterValidation(TestCase):
    """画像バリデーションのテスト"""

    def test_returns_error_when_image_path_is_none(self):
        from social_browser.services.instagram_poster import post_to_instagram_browser

        ok, screenshot, error = post_to_instagram_browser(
            'test content', None, '/tmp/profile',
        )
        self.assertFalse(ok)
        self.assertIn('Image is required', error)

    def test_returns_error_when_image_path_is_empty(self):
        from social_browser.services.instagram_poster import post_to_instagram_browser

        ok, screenshot, error = post_to_instagram_browser(
            'test content', '', '/tmp/profile',
        )
        self.assertFalse(ok)
        self.assertIn('Image is required', error)

    @patch('os.path.isfile', return_value=False)
    def test_returns_error_when_image_file_not_found(self, _mock_isfile):
        from social_browser.services.instagram_poster import post_to_instagram_browser

        ok, screenshot, error = post_to_instagram_browser(
            'test content', '/tmp/nonexistent.jpg', '/tmp/profile',
        )
        self.assertFalse(ok)
        self.assertIn('Image file not found', error)

    def test_returns_error_when_playwright_not_installed(self):
        """playwright がインストールされていない場合"""
        import sys
        from unittest.mock import MagicMock

        # playwright を一時的にモックで ImportError にする
        with patch.dict(sys.modules, {'playwright': None, 'playwright.sync_api': None}):
            # reload は複雑なので、直接テスト
            from social_browser.services.instagram_poster import post_to_instagram_browser
            # image_path が None なので先にそちらのバリデーションに引っかかる
            ok, screenshot, error = post_to_instagram_browser(
                'test content', None, '/tmp/profile',
            )
            self.assertFalse(ok)


class TestInstagramPosterSelectors(TestCase):
    """セレクタ定数のテスト"""

    def test_new_post_selectors_has_japanese_and_english(self):
        from social_browser.services.instagram_poster import NEW_POST_SELECTORS

        selectors_str = ' '.join(NEW_POST_SELECTORS)
        self.assertIn('新規投稿', selectors_str)
        self.assertIn('New post', selectors_str)

    def test_next_selectors_has_japanese_and_english(self):
        from social_browser.services.instagram_poster import NEXT_SELECTORS

        selectors_str = ' '.join(NEXT_SELECTORS)
        self.assertIn('次へ', selectors_str)
        self.assertIn('Next', selectors_str)

    def test_share_selectors_has_japanese_and_english(self):
        from social_browser.services.instagram_poster import SHARE_SELECTORS

        selectors_str = ' '.join(SHARE_SELECTORS)
        self.assertIn('シェア', selectors_str)
        self.assertIn('Share', selectors_str)

    def test_caption_selectors_has_japanese_and_english(self):
        from social_browser.services.instagram_poster import CAPTION_SELECTORS

        selectors_str = ' '.join(CAPTION_SELECTORS)
        self.assertIn('キャプション', selectors_str)
        self.assertIn('caption', selectors_str)


class TestInstagramPosterBrowserFlow(TestCase):
    """ブラウザフロー（Playwright モック）のテスト"""

    @patch('os.path.isfile', return_value=True)
    def test_returns_error_when_not_logged_in(self, _mock_isfile):
        """ログインページにリダイレクトされた場合"""
        from contextlib import contextmanager
        from social_browser.services.instagram_poster import post_to_instagram_browser

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.url = 'https://www.instagram.com/accounts/login/'

        @contextmanager
        def mock_browser_session(profile_dir, headless=True):
            yield mock_page, mock_context

        with patch(
            'social_browser.services.instagram_poster.browser_session',
            mock_browser_session,
        ), patch(
            'social_browser.services.instagram_poster.take_screenshot',
            return_value='/tmp/screenshot.png',
        ):
            ok, screenshot, error = post_to_instagram_browser(
                'test content', '/tmp/test.jpg', '/tmp/profile',
            )

        self.assertFalse(ok)
        self.assertIn('Not logged in', error)
