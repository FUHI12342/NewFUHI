"""X (Twitter) ブラウザ自動投稿 — data-testid セレクタベース"""
import logging

from .browser_service import (
    browser_session,
    random_delay,
    human_type,
    take_screenshot,
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
    screenshot_path = ''
    try:
        with browser_session(profile_dir, headless) as (page, context):
            # X ホームに移動
            page.goto('https://x.com/home', wait_until='networkidle', timeout=30000)
            random_delay(2, 4)

            # ログイン状態チェック
            if 'login' in page.url.lower():
                return False, '', 'Not logged in - session expired'

            # ツイート入力エリア
            tweet_input = page.locator('[data-testid="tweetTextarea_0"]')
            tweet_input.click()
            random_delay(0.5, 1.0)

            # 人間らしく入力
            human_type(page, '[data-testid="tweetTextarea_0"]', content)
            random_delay(1, 2)

            # 投稿ボタンクリック
            post_button = page.locator('[data-testid="tweetButtonInline"]')
            post_button.click()
            random_delay(3, 5)

            # スクリーンショット
            screenshot_path = take_screenshot(page, profile_dir, 'x_post')

            return True, screenshot_path, ''

    except RuntimeError as e:
        return False, '', str(e)
    except Exception as e:
        logger.error("X browser post failed: %s", e, exc_info=True)
        return False, screenshot_path, 'X投稿に失敗しました。サーバーログを確認してください。'
