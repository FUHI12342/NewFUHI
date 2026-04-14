"""gbp_poster のユニットテスト — セレクタフォールバック・画像バリデーション"""
from unittest.mock import MagicMock, patch

from django.test import TestCase


class TestGbpPosterValidation(TestCase):
    """入力バリデーションのテスト"""

    @patch('os.path.isfile', return_value=False)
    def test_returns_error_when_image_file_not_found(self, _mock_isfile):
        from social_browser.services.gbp_poster import post_to_gbp_browser

        ok, screenshot, error = post_to_gbp_browser(
            'test content', '/tmp/profile', image_path='/tmp/nonexistent.jpg',
        )
        self.assertFalse(ok)
        self.assertIn('Image file not found', error)

    def test_image_path_none_is_allowed(self):
        """image_path=None の場合はバリデーションをスキップ"""
        # playwright ImportError でフォールバックされるが、image バリデーション前にそこに到達
        from social_browser.services.gbp_poster import post_to_gbp_browser

        # playwright がない環境では ImportError で false が返る
        ok, screenshot, error = post_to_gbp_browser(
            'test content', '/tmp/profile', image_path=None,
        )
        # エラーは image 関連ではない
        if not ok:
            self.assertNotIn('Image file not found', error)


class TestGbpPosterSelectors(TestCase):
    """セレクタ定数のテスト"""

    def test_create_post_selectors_has_japanese_and_english(self):
        from social_browser.services.gbp_poster import CREATE_POST_SELECTORS

        selectors_str = ' '.join(CREATE_POST_SELECTORS)
        self.assertIn('投稿を作成', selectors_str)
        self.assertIn('Create post', selectors_str)

    def test_publish_selectors_has_japanese_and_english(self):
        from social_browser.services.gbp_poster import PUBLISH_SELECTORS

        selectors_str = ' '.join(PUBLISH_SELECTORS)
        self.assertIn('投稿', selectors_str)
        self.assertIn('Post', selectors_str)

    def test_text_input_selectors_includes_contenteditable(self):
        from social_browser.services.gbp_poster import TEXT_INPUT_SELECTORS

        selectors_str = ' '.join(TEXT_INPUT_SELECTORS)
        self.assertIn('contenteditable', selectors_str)

    def test_post_success_texts_has_japanese_and_english(self):
        from social_browser.services.gbp_poster import POST_SUCCESS_TEXTS

        texts_str = ' '.join(POST_SUCCESS_TEXTS)
        self.assertIn('投稿が公開', texts_str)
        self.assertIn('Post published', texts_str)


class TestGbpPosterBrowserFlow(TestCase):
    """ブラウザフロー（Playwright モック）のテスト"""

    def test_returns_error_when_not_logged_in(self):
        """Google ログインページにリダイレクトされた場合"""
        from social_browser.services.gbp_poster import post_to_gbp_browser

        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.url = 'https://accounts.google.com/signin/v2/identifier'
        mock_context.new_page.return_value = mock_page

        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context

        mock_sync_pw = MagicMock()
        mock_sync_pw.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_sync_pw.return_value.__exit__ = MagicMock(return_value=False)

        with patch(
            'social_browser.services.gbp_poster.create_browser_context',
            return_value=(mock_browser, mock_context),
        ), patch(
            'social_browser.services.gbp_poster.take_screenshot',
            return_value='/tmp/screenshot.png',
        ), patch(
            'playwright.sync_api.sync_playwright', mock_sync_pw,
        ):
            ok, screenshot, error = post_to_gbp_browser(
                'test content', '/tmp/profile',
            )

        self.assertFalse(ok)
        self.assertIn('Not logged in', error)


class TestCheckPostSuccess(TestCase):
    """_check_post_success のテスト"""

    def test_returns_true_for_japanese_success_message(self):
        from social_browser.services.gbp_poster import _check_post_success

        mock_page = MagicMock()
        mock_page.inner_text.return_value = 'ページ上部に「投稿が公開されました」と表示'

        self.assertTrue(_check_post_success(mock_page))

    def test_returns_true_for_english_success_message(self):
        from social_browser.services.gbp_poster import _check_post_success

        mock_page = MagicMock()
        mock_page.inner_text.return_value = 'Post published successfully'

        self.assertTrue(_check_post_success(mock_page))

    def test_returns_false_for_no_success_message(self):
        from social_browser.services.gbp_poster import _check_post_success

        mock_page = MagicMock()
        mock_page.inner_text.return_value = 'Some other page content'

        self.assertFalse(_check_post_success(mock_page))

    def test_returns_false_on_exception(self):
        from social_browser.services.gbp_poster import _check_post_success

        mock_page = MagicMock()
        mock_page.inner_text.side_effect = Exception('timeout')

        self.assertFalse(_check_post_success(mock_page))
