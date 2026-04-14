"""ブラウザ自動投稿 Celery タスク"""
import logging
import os

from celery import shared_task

from social_browser.services.browser_service import VALID_PLATFORMS

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1, default_retry_delay=300)
def task_browser_post(self, session_id, draft_post_id, content, platform):
    """ブラウザ経由で SNS に投稿

    queue='browser_posting', pool=solo で実行。
    """
    # プラットフォームバリデーション
    if platform not in VALID_PLATFORMS:
        logger.error("Invalid platform for browser post: %s", platform)
        return

    from social_browser.models import BrowserSession, BrowserPostLog
    from booking.models import DraftPost, SystemConfig

    # フィーチャーフラグチェック
    if SystemConfig.get('browser_posting_enabled', 'false') != 'true':
        logger.info("Browser posting is disabled via SystemConfig")
        return

    try:
        session = BrowserSession.objects.get(id=session_id)
    except BrowserSession.DoesNotExist:
        logger.error("BrowserSession not found: %s", session_id)
        return

    if session.status != 'active':
        logger.warning("Session %s is not active (status=%s)", session_id, session.status)
        return

    draft = None
    if draft_post_id:
        try:
            draft = DraftPost.objects.get(id=draft_post_id)
        except DraftPost.DoesNotExist:
            logger.warning("DraftPost not found: %s (continuing without reference)", draft_post_id)

    success = False
    screenshot_path = ''
    error = ''

    try:
        if platform == 'x':
            from social_browser.services.x_browser_poster import post_to_x_browser
            success, screenshot_path, error = post_to_x_browser(
                content, session.profile_dir,
            )
        elif platform == 'instagram':
            from social_browser.services.instagram_poster import post_to_instagram_browser
            image_path = draft.image.path if draft and draft.image else ''
            success, screenshot_path, error = post_to_instagram_browser(
                content, image_path, session.profile_dir,
            )
        elif platform == 'gbp':
            from social_browser.services.gbp_poster import post_to_gbp_browser
            success, screenshot_path, error = post_to_gbp_browser(
                content, session.profile_dir,
            )

    except Exception as exc:
        error = str(exc)
        logger.error("Browser post error: %s", exc)

    # ログ記録
    log = BrowserPostLog.objects.create(
        session=session,
        draft_post=draft,
        content=content,
        success=success,
        error_message=error,
    )
    if screenshot_path:
        from django.conf import settings as django_settings
        media_root = getattr(django_settings, 'MEDIA_ROOT', '')
        if media_root and screenshot_path.startswith(media_root):
            log.screenshot.name = os.path.relpath(screenshot_path, media_root)
        else:
            log.screenshot.name = screenshot_path
        log.save(update_fields=['screenshot'])

    # PostHistory 記録（ブラウザ投稿でも履歴を残す）
    from booking.models import PostHistory
    from django.utils import timezone as tz

    history = PostHistory.objects.create(
        store=session.store,
        platform=platform,
        trigger_type='manual',
        content=content,
        status='posted' if success else 'failed',
        error_message='' if success else error,
    )
    if success:
        history.posted_at = tz.now()
        history.save(update_fields=['posted_at'])

    # BAN検出: セッションを無効化し、リトライしない
    if not success and error and 'suspended' in error.lower():
        session.status = 'expired'
        session.save(update_fields=['status', 'updated_at'])
        logger.critical("Account suspended for session %s, disabling", session_id)
        return  # suspended時はリトライしない

    if not success:
        raise self.retry(exc=Exception(error))
