"""Instagram ブラウザ自動投稿"""
import logging

from .browser_service import (
    create_browser_context, save_storage_state,
    _random_delay, _human_type, take_screenshot,
)

logger = logging.getLogger(__name__)


def post_to_instagram_browser(content, image_path, profile_dir, headless=True):
    """Instagram にブラウザ経由で投稿

    Args:
        content: 投稿テキスト（キャプション）
        image_path: 投稿画像のファイルパス
        profile_dir: ブラウザプロファイルディレクトリ
        headless: ヘッドレスモード

    Returns:
        (success: bool, screenshot_path: str, error: str)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, '', 'playwright is not installed'

    if not image_path:
        return False, '', 'Image is required for Instagram posts'

    screenshot_path = ''
    try:
        with sync_playwright() as p:
            browser, context = create_browser_context(p, profile_dir, headless)
            page = context.new_page()

            # Instagram に移動
            page.goto('https://www.instagram.com/', wait_until='networkidle', timeout=30000)
            _random_delay(2, 4)

            # ログインチェック
            if 'login' in page.url.lower() or 'accounts/login' in page.url:
                browser.close()
                return False, '', 'Not logged in - session expired'

            # 新規投稿ボタン
            page.locator('svg[aria-label="新規投稿"]').click()
            _random_delay(1, 2)

            # 画像アップロード
            file_input = page.locator('input[type="file"]')
            file_input.set_input_files(image_path)
            _random_delay(2, 3)

            # 次へボタン（2回）
            for _ in range(2):
                next_button = page.locator('button:has-text("次へ")')
                if next_button.is_visible():
                    next_button.click()
                    _random_delay(1, 2)

            # キャプション入力
            caption_input = page.locator('textarea[aria-label="キャプションを入力…"]')
            if caption_input.is_visible():
                caption_input.fill(content)
                _random_delay(1, 2)

            # シェアボタン
            share_button = page.locator('button:has-text("シェア")')
            if share_button.is_visible():
                share_button.click()
                _random_delay(3, 5)

            screenshot_path = take_screenshot(page, profile_dir, 'instagram_post')
            save_storage_state(context, profile_dir)
            browser.close()
            return True, screenshot_path, ''

    except Exception as e:
        logger.error("Instagram browser post failed: %s", e)
        return False, screenshot_path, str(e)
