"""Playwright ラッパー — ブラウザ自動投稿の共通基盤"""
import logging
import os
import random
import stat
import time
from contextlib import contextmanager

from django.conf import settings

logger = logging.getLogger(__name__)

# プラットフォームバリデーション用
VALID_PLATFORMS = frozenset({'x', 'instagram', 'gbp', 'tiktok'})


def get_profile_dir(store_id, platform):
    """ブラウザプロファイルディレクトリのパスを返す"""
    media_root = getattr(settings, 'MEDIA_ROOT', '/tmp/media')
    path = os.path.join(media_root, 'browser_profiles', str(store_id), platform)
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def random_delay(min_sec=1.0, max_sec=3.0):
    """ランダム遅延（人間らしい動作）"""
    time.sleep(random.uniform(min_sec, max_sec))


# 後方互換
_random_delay = random_delay


def human_type(page, selector, text, delay_ms=30):
    """人間らしいタイピング速度で入力"""
    page.click(selector)
    random_delay(0.3, 0.8)
    for char in text:
        page.keyboard.type(char, delay=max(0, delay_ms + random.randint(-10, 20)))
    random_delay(0.5, 1.0)


# 後方互換
_human_type = human_type


def _get_browser_args():
    """Chromium 起動引数を環境に応じて生成"""
    args = ['--disable-gpu', '--disable-dev-shm-usage']
    # root実行時のみsandbox無効化（Docker/CI環境対応）
    if os.getuid() == 0:
        args.append('--no-sandbox')
    return args


def create_browser_context(playwright_instance, profile_dir, headless=True):
    """永続コンテキストを作成（セッション再利用）

    Args:
        playwright_instance: playwright.sync_api.Playwright
        profile_dir: プロファイル保存ディレクトリ
        headless: ヘッドレスモード

    Returns:
        (browser, context)
    """
    browser = playwright_instance.chromium.launch(
        headless=headless,
        args=_get_browser_args(),
    )
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
        viewport={'width': 1280, 'height': 720},
        storage_state=_get_storage_state(profile_dir),
    )
    return browser, context


def _get_storage_state(profile_dir):
    """保存済みストレージ状態を読み込む"""
    state_file = os.path.join(profile_dir, 'storage_state.json')
    if os.path.exists(state_file):
        return state_file
    return None


def save_storage_state(context, profile_dir):
    """ストレージ状態を保存（Cookie + LocalStorage）"""
    state_file = os.path.join(profile_dir, 'storage_state.json')
    context.storage_state(path=state_file)
    # セッションCookieを含むため、オーナーのみ読み書き可能に制限
    os.chmod(state_file, stat.S_IRUSR | stat.S_IWUSR)
    logger.info("Storage state saved for %s/%s",
                os.path.basename(os.path.dirname(profile_dir)),
                os.path.basename(profile_dir))


def take_screenshot(page, profile_dir, name='post'):
    """デバッグ用スクリーンショット保存"""
    screenshots_dir = os.path.join(profile_dir, 'screenshots')
    os.makedirs(screenshots_dir, exist_ok=True)
    path = os.path.join(screenshots_dir, f'{name}_{int(time.time())}.png')
    page.screenshot(path=path)
    return path


def wait_and_click(page, selectors, timeout=10000, step_name=''):
    """複数セレクタをフォールバック付きで待機・クリック

    Args:
        page: Playwright Page
        selectors: セレクタのリスト（先頭から順に試行）
        timeout: 待機タイムアウト (ms)
        step_name: デバッグ用ステップ名

    Returns:
        True if clicked successfully

    Raises:
        TimeoutError: 全セレクタがタイムアウトした場合
    """
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state='visible', timeout=timeout)
            locator.click()
            logger.debug("Clicked '%s' via selector: %s", step_name, selector)
            _random_delay(0.5, 1.5)
            return True
        except Exception:
            logger.debug("Selector not found for '%s': %s", step_name, selector)
            continue
    raise TimeoutError(f"No matching selector found for step '{step_name}': {selectors}")


def wait_for_input(page, selectors, timeout=10000, step_name=''):
    """入力フィールドを複数セレクタから待機・取得

    Args:
        page: Playwright Page
        selectors: セレクタのリスト
        timeout: 待機タイムアウト (ms)
        step_name: デバッグ用ステップ名

    Returns:
        見つかった Locator

    Raises:
        TimeoutError: 全セレクタがタイムアウトした場合
    """
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state='visible', timeout=timeout)
            logger.debug("Found input '%s' via selector: %s", step_name, selector)
            return locator
        except Exception:
            logger.debug("Input selector not found for '%s': %s", step_name, selector)
            continue
    raise TimeoutError(f"No matching input found for step '{step_name}': {selectors}")


def create_browser_context_mobile(playwright_instance, profile_dir, headless=True):
    """モバイル viewport でコンテキストを作成（Instagram 用）

    Args:
        playwright_instance: playwright.sync_api.Playwright
        profile_dir: プロファイル保存ディレクトリ
        headless: ヘッドレスモード

    Returns:
        (browser, context)
    """
    browser = playwright_instance.chromium.launch(
        headless=headless,
        args=_get_browser_args(),
    )
    context = browser.new_context(
        user_agent=(
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) '
            'Version/17.0 Mobile/15E148 Safari/604.1'
        ),
        viewport={'width': 390, 'height': 844},
        is_mobile=True,
        has_touch=True,
        storage_state=_get_storage_state(profile_dir),
    )
    return browser, context


@contextmanager
def browser_session(profile_dir, headless=True, mobile=False):
    """ブラウザセッションのコンテキストマネージャ（リソースリーク防止）

    Usage:
        with browser_session(profile_dir) as (page, context):
            page.goto('https://...')
            # ... 操作 ...
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('playwright is not installed')

    with sync_playwright() as p:
        create_fn = create_browser_context_mobile if mobile else create_browser_context
        browser, context = create_fn(p, profile_dir, headless)
        try:
            page = context.new_page()
            yield page, context
            save_storage_state(context, profile_dir)
        finally:
            browser.close()
