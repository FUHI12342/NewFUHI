"""投稿ディスパッチャー: レート制限チェック + 投稿 + 履歴記録"""
import json
import logging

from django.utils import timezone

from booking.services.post_generator import build_content
from booking.services.x_posting_service import (
    PostResult,
    XApiError,
    RateLimitError,
    post_tweet,
)
from booking.services.x_rate_limiter import can_post, record_post

logger = logging.getLogger(__name__)

MAX_RETRY_COUNT = 2  # 失敗もカウント消費のため少なめ


def dispatch_post(store_id, trigger_type, context_data):
    """メインディスパッチ関数。Celery タスクから呼ばれる。

    1. SocialAccount取得
    2. PostTemplate取得
    3. コンテンツ生成
    4. PostHistory作成
    5. レート制限チェック
    6. X API投稿
    7. PostHistory更新
    """
    from booking.models import SocialAccount, PostTemplate, PostHistory, Store

    # context_data が文字列の場合はJSONパース
    if isinstance(context_data, str):
        context_data = json.loads(context_data)

    try:
        store = Store.objects.get(id=store_id)
    except Store.DoesNotExist:
        logger.error("Store not found: %s", store_id)
        return

    # 1. アクティブなSocialAccount
    try:
        account = SocialAccount.objects.get(
            store=store, platform='x', is_active=True,
        )
    except SocialAccount.DoesNotExist:
        logger.info("No active X account for store %s", store.name)
        return

    # 2. アクティブなPostTemplate
    try:
        template = PostTemplate.objects.get(
            store=store, platform='x', trigger_type=trigger_type, is_active=True,
        )
    except PostTemplate.DoesNotExist:
        logger.info(
            "No active template for store %s, trigger %s",
            store.name, trigger_type,
        )
        return

    # 3. コンテンツ生成
    try:
        content = build_content(trigger_type, store, context_data, template)
    except Exception as e:
        logger.error("Content generation failed: %s", e)
        PostHistory.objects.create(
            store=store,
            platform='x',
            trigger_type=trigger_type,
            content='',
            status='failed',
            error_message=f'Content generation failed: {e}',
        )
        return

    if not content:
        logger.warning("Empty content generated for store %s", store.name)
        return

    # 4. PostHistory作成 (pending)
    history = PostHistory.objects.create(
        store=store,
        platform='x',
        trigger_type=trigger_type,
        content=content,
        status='pending',
    )

    # 5. レート制限チェック
    allowed, reason = can_post(store_id)
    if not allowed:
        history.status = 'skipped'
        history.error_message = f'Rate limit: {reason}'
        history.save(update_fields=['status', 'error_message'])
        logger.info("Post skipped for store %s: %s", store.name, reason)
        return

    # 6. X API投稿
    _execute_post(account, content, history, store_id)


def _execute_post(account, content, history, store_id):
    """X API投稿を実行し、PostHistoryを更新する。"""
    try:
        result = post_tweet(account, content)
    except RateLimitError as e:
        history.status = 'skipped'
        history.error_message = f'X API rate limited: {e}'
        history.save(update_fields=['status', 'error_message'])
        logger.warning("X API rate limited for store %s: %s", history.store.name, e)
        return
    except XApiError as e:
        history.status = 'failed'
        history.error_message = str(e)[:1000]
        history.retry_count += 1
        history.save(update_fields=['status', 'error_message', 'retry_count'])
        logger.error("X API error for store %s: %s", history.store.name, e)
        return

    if result.success:
        history.status = 'posted'
        history.external_post_id = result.external_post_id
        history.posted_at = timezone.now()
        history.save(
            update_fields=['status', 'external_post_id', 'posted_at'],
        )
        record_post(store_id)
        logger.info(
            "Posted to X for store %s: %s",
            history.store.name, result.external_post_id,
        )
    else:
        history.status = 'failed'
        history.error_message = result.error_message
        history.retry_count += 1
        history.save(update_fields=['status', 'error_message', 'retry_count'])


def retry_failed_post(post_history_id):
    """失敗した投稿をリトライ"""
    from booking.models import PostHistory, SocialAccount

    try:
        history = PostHistory.objects.get(id=post_history_id)
    except PostHistory.DoesNotExist:
        logger.error("PostHistory not found: %s", post_history_id)
        return

    if history.status != 'failed':
        logger.info("PostHistory %s is not in failed status", post_history_id)
        return

    if history.retry_count >= MAX_RETRY_COUNT:
        logger.warning(
            "PostHistory %s exceeded max retry count (%d)",
            post_history_id, MAX_RETRY_COUNT,
        )
        return

    try:
        account = SocialAccount.objects.get(
            store=history.store, platform='x', is_active=True,
        )
    except SocialAccount.DoesNotExist:
        logger.error("No active X account for retry: store %s", history.store.name)
        return

    allowed, reason = can_post(history.store_id)
    if not allowed:
        logger.info("Retry skipped for %s: %s", post_history_id, reason)
        return

    _execute_post(account, history.content, history, history.store_id)
