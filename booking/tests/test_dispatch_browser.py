"""_dispatch_browser_post + dispatch_draft_post ブラウザ連携テスト"""
from unittest.mock import MagicMock, patch

from django.test import TestCase


class TestDispatchDraftPostRouting(TestCase):
    """dispatch_draft_post のプラットフォームルーティングテスト"""

    @patch('booking.services.post_dispatcher._dispatch_browser_post')
    def test_instagram_routes_to_browser(self, mock_browser):
        """Instagram は _dispatch_browser_post にルーティング"""
        from booking.services.post_dispatcher import dispatch_draft_post

        mock_browser.return_value = (True, 'ブラウザ投稿完了')
        draft = MagicMock()

        ok, msg = dispatch_draft_post(draft, 'instagram')

        self.assertTrue(ok)
        mock_browser.assert_called_once_with(draft, 'instagram')

    @patch('booking.services.post_dispatcher._dispatch_browser_post')
    def test_gbp_routes_to_browser(self, mock_browser):
        """GBP は _dispatch_browser_post にルーティング"""
        from booking.services.post_dispatcher import dispatch_draft_post

        mock_browser.return_value = (True, 'ブラウザ投稿完了')
        draft = MagicMock()

        ok, msg = dispatch_draft_post(draft, 'gbp')

        self.assertTrue(ok)
        mock_browser.assert_called_once_with(draft, 'gbp')

    @patch('booking.models.SocialAccount.objects')
    @patch('booking.services.post_dispatcher.append_booking_url')
    @patch('booking.services.post_dispatcher.can_post')
    @patch('booking.services.post_dispatcher._execute_post')
    def test_x_routes_to_api(self, mock_exec, mock_can, mock_append, mock_sa):
        """X は API 投稿にルーティング"""
        from booking.services.post_dispatcher import dispatch_draft_post

        mock_account = MagicMock()
        mock_sa.get.return_value = mock_account
        mock_append.return_value = 'content with url'
        mock_can.return_value = (True, '')

        draft = MagicMock()
        draft.content = 'test'
        draft.store_id = 1

        with patch('booking.models.PostHistory.objects') as mock_ph:
            mock_history = MagicMock()
            mock_history.status = 'posted'
            mock_history.external_post_id = '12345'
            mock_ph.create.return_value = mock_history
            mock_history.refresh_from_db = MagicMock()

            ok, msg = dispatch_draft_post(draft, 'x')

        mock_exec.assert_called_once()


class TestDispatchBrowserPost(TestCase):
    """_dispatch_browser_post の詳細テスト"""

    @patch('social_browser.services.browser_service.get_profile_dir', return_value='/tmp/profile')
    @patch('social_browser.models.BrowserSession.objects')
    def test_returns_error_when_session_setup_required(self, mock_session_qs, _mock_dir):
        """セッション未設定時にエラーを返す"""
        from booking.services.post_dispatcher import _dispatch_browser_post

        mock_session = MagicMock()
        mock_session.status = 'setup_required'
        mock_session_qs.get_or_create.return_value = (mock_session, False)

        draft = MagicMock()
        draft.store_id = 1

        ok, msg = _dispatch_browser_post(draft, 'instagram')

        self.assertFalse(ok)
        self.assertIn('未設定', msg)

    @patch('social_browser.services.browser_service.get_profile_dir', return_value='/tmp/profile')
    @patch('social_browser.models.BrowserSession.objects')
    def test_returns_error_when_session_expired(self, mock_session_qs, _mock_dir):
        """セッション期限切れ時にエラーを返す"""
        from booking.services.post_dispatcher import _dispatch_browser_post

        mock_session = MagicMock()
        mock_session.status = 'expired'
        mock_session_qs.get_or_create.return_value = (mock_session, False)

        draft = MagicMock()
        draft.store_id = 1

        ok, msg = _dispatch_browser_post(draft, 'gbp')

        self.assertFalse(ok)
        self.assertIn('期限切れ', msg)

    @patch('social_browser.services.browser_service.get_profile_dir', return_value='/tmp/profile')
    @patch('social_browser.models.BrowserPostLog.objects')
    @patch('booking.models.PostHistory.objects')
    @patch('social_browser.models.BrowserSession.objects')
    @patch('social_browser.services.instagram_poster.post_to_instagram_browser')
    def test_instagram_success_creates_post_history(
        self, mock_poster, mock_session_qs, mock_ph, mock_log, _mock_dir,
    ):
        """Instagram 投稿成功時に PostHistory が posted で作成される"""
        from booking.services.post_dispatcher import _dispatch_browser_post

        mock_session = MagicMock()
        mock_session.status = 'active'
        mock_session.profile_dir = '/tmp/profile'
        mock_session_qs.get_or_create.return_value = (mock_session, False)

        mock_poster.return_value = (True, '/tmp/screenshot.png', '')

        mock_history = MagicMock()
        mock_ph.create.return_value = mock_history

        draft = MagicMock()
        draft.store_id = 1
        draft.content = 'test caption'
        draft.image = MagicMock()
        draft.image.path = '/tmp/test.jpg'
        draft.image.__bool__ = lambda self: True

        ok, msg = _dispatch_browser_post(draft, 'instagram')

        self.assertTrue(ok)
        mock_ph.create.assert_called_once()
        # PostHistory が posted で更新されたか確認
        mock_history.save.assert_called_once()

    @patch('social_browser.services.browser_service.get_profile_dir', return_value='/tmp/profile')
    @patch('social_browser.models.BrowserPostLog.objects')
    @patch('booking.models.PostHistory.objects')
    @patch('social_browser.models.BrowserSession.objects')
    @patch('social_browser.services.gbp_poster.post_to_gbp_browser')
    def test_gbp_failure_creates_failed_post_history(
        self, mock_poster, mock_session_qs, mock_ph, mock_log, _mock_dir,
    ):
        """GBP 投稿失敗時に PostHistory が failed で記録される"""
        from booking.services.post_dispatcher import _dispatch_browser_post

        mock_session = MagicMock()
        mock_session.status = 'active'
        mock_session.profile_dir = '/tmp/profile'
        mock_session_qs.get_or_create.return_value = (mock_session, False)

        mock_poster.return_value = (False, '', 'Could not find create post button')

        mock_history = MagicMock()
        mock_history.retry_count = 0
        mock_ph.create.return_value = mock_history

        draft = MagicMock()
        draft.store_id = 1
        draft.content = 'test content'
        draft.image = None

        ok, msg = _dispatch_browser_post(draft, 'gbp')

        self.assertFalse(ok)
        mock_log.create.assert_called_once()


class TestBrowserServiceHelpers(TestCase):
    """wait_and_click, wait_for_input のテスト"""

    def test_wait_and_click_tries_fallback(self):
        """最初のセレクタが失敗しても次のセレクタで成功"""
        from social_browser.services.browser_service import wait_and_click

        mock_page = MagicMock()
        first_locator = MagicMock()
        first_locator.wait_for.side_effect = Exception('not found')
        second_locator = MagicMock()

        call_count = 0

        def mock_locator(selector):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:
                result.first = first_locator
            else:
                result.first = second_locator
            return result

        mock_page.locator = mock_locator

        result = wait_and_click(
            mock_page, ['selector1', 'selector2'], timeout=1000, step_name='test',
        )

        self.assertTrue(result)
        second_locator.click.assert_called_once()

    def test_wait_and_click_raises_timeout_when_all_fail(self):
        """全セレクタ失敗時に TimeoutError"""
        from social_browser.services.browser_service import wait_and_click

        mock_page = MagicMock()
        failing_locator = MagicMock()
        failing_locator.wait_for.side_effect = Exception('not found')

        mock_result = MagicMock()
        mock_result.first = failing_locator
        mock_page.locator.return_value = mock_result

        with self.assertRaises(TimeoutError):
            wait_and_click(
                mock_page, ['sel1', 'sel2'], timeout=1000, step_name='test',
            )

    def test_wait_for_input_returns_locator(self):
        """入力フィールドが見つかった場合に Locator を返す"""
        from social_browser.services.browser_service import wait_for_input

        mock_page = MagicMock()
        found_locator = MagicMock()
        mock_result = MagicMock()
        mock_result.first = found_locator
        mock_page.locator.return_value = mock_result

        result = wait_for_input(
            mock_page, ['input[name="test"]'], timeout=1000, step_name='test',
        )

        self.assertEqual(result, found_locator)
