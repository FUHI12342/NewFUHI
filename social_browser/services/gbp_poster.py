"""Google Business Profile ブラウザ自動投稿 — 多言語セレクタ + 画像対応"""
import logging
import os

from .browser_service import (
    browser_session,
    random_delay,
    take_screenshot,
    wait_and_click,
    wait_for_input,
)

logger = logging.getLogger(__name__)

# --- 多言語セレクタ（日本語 → 英語 フォールバック） ---
CREATE_POST_SELECTORS = [
    'button:has-text("投稿を作成")',
    'button:has-text("最新情報を追加")',
    'button:has-text("Create post")',
    'button:has-text("Add update")',
    'button:has-text("Add post")',
    'a:has-text("投稿を作成")',
    'a:has-text("Create post")',
]

TEXT_INPUT_SELECTORS = [
    'textarea[aria-label*="投稿"]',
    'textarea[aria-label*="post"]',
    '[contenteditable="true"]',
    'textarea',
]

PUBLISH_SELECTORS = [
    'button:has-text("投稿")',
    'button:has-text("公開")',
    'button:has-text("Post")',
    'button:has-text("Publish")',
    'button:has-text("送信")',
    'button:has-text("Submit")',
]

POST_SUCCESS_TEXTS = [
    '投稿が公開されました',
    '投稿が作成されました',
    'Post published',
    'Post created',
    'Your update is live',
]


def post_to_gbp_browser(content, profile_dir, headless=True, image_path=None):
    """GBP にブラウザ経由で投稿

    Args:
        content: 投稿テキスト
        profile_dir: ブラウザプロファイルディレクトリ
        headless: ヘッドレスモード
        image_path: 画像ファイルパス（オプション）

    Returns:
        (success: bool, screenshot_path: str, error: str)
    """
    # 画像バリデーション（オプション）
    if image_path and not os.path.isfile(image_path):
        return False, '', f'Image file not found: {image_path}'

    screenshot_path = ''
    try:
        with browser_session(profile_dir, headless) as (page, context):
            # Step 1: GBP 管理画面へ移動
            page.goto(
                'https://business.google.com/',
                wait_until='networkidle',
                timeout=30000,
            )
            random_delay(2, 4)

            # ログインチェック
            if 'accounts.google.com' in page.url:
                screenshot_path = take_screenshot(page, profile_dir, 'gbp_login_required')
                return False, screenshot_path, 'Not logged in to Google - session expired'

            screenshot_path = take_screenshot(page, profile_dir, 'gbp_step1_home')

            # Step 2: 「投稿を作成」ボタン
            try:
                wait_and_click(
                    page, CREATE_POST_SELECTORS,
                    timeout=15000,
                    step_name='投稿を作成',
                )
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'gbp_step2_no_create')
                return False, screenshot_path, str(e)
            random_delay(1, 2)
            screenshot_path = take_screenshot(page, profile_dir, 'gbp_step2_create_clicked')

            # Step 3: 画像アップロード（オプション）
            if image_path:
                try:
                    file_input = page.locator('input[type="file"]').first
                    file_input.wait_for(state='attached', timeout=5000)
                    file_input.set_input_files(image_path)
                    random_delay(2, 3)
                    screenshot_path = take_screenshot(page, profile_dir, 'gbp_step3_image')
                except Exception:
                    logger.warning("GBP image upload skipped - file input not found")

            # Step 4: テキスト入力
            try:
                text_el = wait_for_input(
                    page, TEXT_INPUT_SELECTORS,
                    timeout=10000,
                    step_name='テキスト入力',
                )
                tag_name = text_el.evaluate('el => el.tagName')
                if tag_name == 'TEXTAREA':
                    text_el.fill(content)
                else:
                    text_el.click()
                    page.keyboard.type(content, delay=20)
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'gbp_step4_no_input')
                return False, screenshot_path, str(e)
            random_delay(1, 2)
            screenshot_path = take_screenshot(page, profile_dir, 'gbp_step4_text_done')

            # Step 5: 投稿ボタン
            try:
                wait_and_click(
                    page, PUBLISH_SELECTORS,
                    timeout=10000,
                    step_name='投稿公開',
                )
            except TimeoutError as e:
                screenshot_path = take_screenshot(page, profile_dir, 'gbp_step5_no_publish')
                return False, screenshot_path, str(e)

            random_delay(3, 5)
            screenshot_path = take_screenshot(page, profile_dir, 'gbp_step5_published')

            # Step 6: 成功確認（オプション）
            success_confirmed = _check_post_success(page)
            if success_confirmed:
                logger.info("GBP post success confirmed via UI message")

            return True, screenshot_path, ''

    except RuntimeError as e:
        return False, '', str(e)
    except Exception as e:
        logger.error("GBP browser post failed: %s", e, exc_info=True)
        return False, screenshot_path, 'GBP投稿に失敗しました。サーバーログを確認してください。'


def _check_post_success(page):
    """投稿成功メッセージを画面から検出"""
    try:
        body_text = page.inner_text('body', timeout=3000)
        return any(text in body_text for text in POST_SUCCESS_TEXTS)
    except Exception:
        return False
