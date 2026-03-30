"""X (Twitter) ブラウザ自動投稿 — data-testid セレクタベース"""
import logging

from .browser_service import (
    create_browser_context, save_storage_state,
    _random_delay, _human_type, take_screenshot,
)

logger = logging.getLogger(__name__)


def post_to_x_browser(content, profile_dir, headless=True):
    """X にブラウザ経由で投稿

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

            # X ホームに移動
            page.goto('https://x.com/home', wait_until='networkidle', timeout=30000)
            _random_delay(2, 4)

            # ログイン状態チェック
            if 'login' in page.url.lower():
                browser.close()
                return False, '', 'Not logged in - session expired'

            # ツイート入力エリア
            tweet_input = page.locator('[data-testid="tweetTextarea_0"]')
            tweet_input.click()
            _random_delay(0.5, 1.0)

            # 人間らしく入力
            _human_type(page, '[data-testid="tweetTextarea_0"]', content)
            _random_delay(1, 2)

            # 投稿ボタンクリック
            post_button = page.locator('[data-testid="tweetButtonInline"]')
            post_button.click()
            _random_delay(3, 5)

            # スクリーンショット
            screenshot_path = take_screenshot(page, profile_dir, 'x_post')

            # ストレージ状態保存
            save_storage_state(context, profile_dir)
            browser.close()

            return True, screenshot_path, ''

    except Exception as e:
        logger.error("X browser post failed: %s", e)
        return False, screenshot_path, str(e)
