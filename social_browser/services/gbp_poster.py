"""Google Business Profile ブラウザ自動投稿"""
import logging

from .browser_service import (
    create_browser_context, save_storage_state,
    _random_delay, _human_type, take_screenshot,
)

logger = logging.getLogger(__name__)


def post_to_gbp_browser(content, profile_dir, headless=True):
    """GBP にブラウザ経由で投稿

    Args:
        content: 投稿テキスト
        profile_dir: ブラウザプロファイルディレクトリ
        headless: ヘッドレスモード

    Returns:
        (success: bool, screenshot_path: str, error: str)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, '', 'playwright is not installed'

    screenshot_path = ''
    try:
        with sync_playwright() as p:
            browser, context = create_browser_context(p, profile_dir, headless)
            page = context.new_page()

            # GBP 管理画面へ移動
            page.goto(
                'https://business.google.com/',
                wait_until='networkidle', timeout=30000,
            )
            _random_delay(2, 4)

            # ログインチェック
            if 'accounts.google.com' in page.url:
                browser.close()
                return False, '', 'Not logged in to Google - session expired'

            # 「投稿を作成」または「最新情報を追加」ボタンを探す
            create_post = page.locator('button:has-text("投稿を作成"), button:has-text("最新情報を追加")')
            if create_post.is_visible():
                create_post.first.click()
                _random_delay(1, 2)
            else:
                browser.close()
                return False, '', 'Could not find create post button'

            # テキスト入力
            text_area = page.locator('textarea, [contenteditable="true"]').first
            if text_area.is_visible():
                text_area.fill(content)
                _random_delay(1, 2)
            else:
                browser.close()
                return False, '', 'Could not find text input area'

            # 投稿ボタン
            post_button = page.locator('button:has-text("投稿"), button:has-text("公開")')
            if post_button.is_visible():
                post_button.first.click()
                _random_delay(3, 5)
            else:
                browser.close()
                return False, '', 'Could not find publish button'

            screenshot_path = take_screenshot(page, profile_dir, 'gbp_post')
            save_storage_state(context, profile_dir)
            browser.close()
            return True, screenshot_path, ''

    except Exception as e:
        logger.error("GBP browser post failed: %s", e)
        return False, screenshot_path, str(e)
