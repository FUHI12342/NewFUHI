"""Instagram ブラウザ自動投稿 — 多言語セレクタ + 堅牢待機"""
import logging
import os

from .browser_service import (
    create_browser_context,
    save_storage_state,
    _random_delay,
    take_screenshot,
    wait_and_click,
    wait_for_input,
)

logger = logging.getLogger(__name__)

# --- 多言語セレクタ（日本語 → 英語 → data-testid フォールバック） ---
NEW_POST_SELECTORS = [
    'svg[aria-label="新規投稿"]',
    'svg[aria-label="New post"]',
    'svg[aria-label="New Post"]',
    '[data-testid="new-post-button"]',
    'a[href="/create/style/"]',
    'a[href="/create/select/"]',
]

NEXT_SELECTORS = [
    'button:has-text("次へ")',
    'button:has-text("Next")',
    '[role="button"]:has-text("Next")',
    '[role="button"]:has-text("次へ")',
]

SHARE_SELECTORS = [
    'button:has-text("シェア")',
    'button:has-text("シェアする")',
    'button:has-text("Share")',
    'button:has-text("投稿する")',
    'button:has-text("Post")',
]

CAPTION_SELECTORS = [
    'textarea[aria-label="キャプションを入力…"]',
    'textarea[aria-label="Write a caption..."]',
    'textarea[aria-label="Write a caption…"]',
    'div[role="textbox"][contenteditable="true"]',
    'textarea[placeholder*="キャプション"]',
    'textarea[placeholder*="caption"]',
]


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

    # 画像バリデーション
    if not image_path:
        return False, '', 'Image is required for Instagram posts'
    if not os.path.isfile(image_path):
        return False, '', f'Image file not found: {image_path}'

    screenshot_path = ''
    try:
        with sync_playwright() as p:
            browser, context = create_browser_context(p, profile_dir, headless)
            page = context.new_page()

            # Step 1: Instagram に移動
            page.goto(
                'https://www.instagram.com/',
                wait_until='networkidle',
                timeout=30000,
            )
            _random_delay(2, 4)

            # ログインチェック
            if 'login' in page.url.lower() or 'accounts/login' in page.url:
                screenshot_path = take_screenshot(page, profile_dir, 'ig_login_required')
                browser.close()
                return False, screenshot_path, 'Not logged in - session expired'

            screenshot_path = take_screenshot(page, profile_dir, 'ig_step1_home')

            # Step 2: 新規投稿ボタン
            try:
                wait_and_click(page, NEW_POST_SELECTORS, timeout=10000, step_name='新規投稿')
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'ig_step2_no_newpost')
                browser.close()
                return False, screenshot_path, str(e)
            _random_delay(1, 2)
            screenshot_path = take_screenshot(page, profile_dir, 'ig_step2_newpost_clicked')

            # Step 3: 画像アップロード
            try:
                file_input = page.locator('input[type="file"]').first
                file_input.wait_for(state='attached', timeout=10000)
                file_input.set_input_files(image_path)
            except Exception as e:
                screenshot_path = take_screenshot(page, profile_dir, 'ig_step3_upload_fail')
                browser.close()
                return False, screenshot_path, f'Image upload failed: {e}'
            _random_delay(2, 3)
            screenshot_path = take_screenshot(page, profile_dir, 'ig_step3_uploaded')

            # Step 4: 「次へ」ボタン（2回クリック）
            for i in range(2):
                try:
                    wait_and_click(
                        page, NEXT_SELECTORS,
                        timeout=10000,
                        step_name=f'次へ({i + 1})',
                    )
                except TimeoutError:
                    logger.warning("Next button not found at step %d, continuing", i + 1)
                _random_delay(1, 2)

            screenshot_path = take_screenshot(page, profile_dir, 'ig_step4_next_done')

            # Step 5: キャプション入力
            try:
                caption_el = wait_for_input(
                    page, CAPTION_SELECTORS,
                    timeout=10000,
                    step_name='キャプション',
                )
                # contenteditable の場合は fill でなく type
                tag_name = caption_el.evaluate('el => el.tagName')
                if tag_name == 'TEXTAREA':
                    caption_el.fill(content)
                else:
                    caption_el.click()
                    page.keyboard.type(content, delay=20)
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'ig_step5_no_caption')
                browser.close()
                return False, screenshot_path, str(e)
            _random_delay(1, 2)
            screenshot_path = take_screenshot(page, profile_dir, 'ig_step5_caption_done')

            # Step 6: シェアボタン
            try:
                wait_and_click(page, SHARE_SELECTORS, timeout=10000, step_name='シェア')
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'ig_step6_no_share')
                browser.close()
                return False, screenshot_path, str(e)

            _random_delay(3, 5)
            screenshot_path = take_screenshot(page, profile_dir, 'ig_step6_shared')

            save_storage_state(context, profile_dir)
            browser.close()
            return True, screenshot_path, ''

    except Exception as e:
        logger.error("Instagram browser post failed: %s", e)
        return False, screenshot_path, str(e)
