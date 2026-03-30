"""X API レート制限サービス: Redis ベースの日次/月次カウンター"""
import logging
import time

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# 制限値
MONTHLY_APP_LIMIT = 480      # 500 - 20 safety margin
MONTHLY_STORE_LIMIT = 50     # 店舗あたりデフォルト上限
DAILY_APP_LIMIT = 16         # 17 - 1 buffer

# アラートレベル閾値 (月間使用率)
ALERT_YELLOW = 0.70
ALERT_RED = 0.90


def _get_redis():
    """Celery broker URL からRedisクライアントを取得"""
    return redis.Redis.from_url(
        settings.CELERY_BROKER_URL,
        decode_responses=True,
    )


def _month_key():
    """現在月のキー (例: 2026-03)"""
    return time.strftime('%Y-%m')


def can_post(store_id):
    """投稿可能かチェック。(can_post, reason) を返す。"""
    try:
        r = _get_redis()
    except Exception as e:
        logger.error("Redis connection failed for rate limiter: %s", e)
        return (False, 'redis_unavailable')

    month = _month_key()

    # 1. 月間アプリ全体
    app_count = r.get(f'x_api:app_posts:{month}')
    app_count = int(app_count) if app_count else 0
    if app_count >= MONTHLY_APP_LIMIT:
        return (False, f'monthly_app_limit ({app_count}/{MONTHLY_APP_LIMIT})')

    # 2. 月間店舗別
    store_count = r.get(f'x_api:store_posts:{store_id}:{month}')
    store_count = int(store_count) if store_count else 0
    if store_count >= MONTHLY_STORE_LIMIT:
        return (False, f'monthly_store_limit ({store_count}/{MONTHLY_STORE_LIMIT})')

    # 3. 日次スライディングウィンドウ (Sorted Set)
    now = time.time()
    window_start = now - 86400  # 24時間前
    r.zremrangebyscore('x_api:daily_posts', '-inf', window_start)
    daily_count = r.zcard('x_api:daily_posts')
    if daily_count >= DAILY_APP_LIMIT:
        return (False, f'daily_app_limit ({daily_count}/{DAILY_APP_LIMIT})')

    return (True, 'ok')


def record_post(store_id):
    """投稿成功後にカウンターをインクリメント"""
    try:
        r = _get_redis()
    except Exception as e:
        logger.error("Redis connection failed for recording post: %s", e)
        return

    month = _month_key()
    now = time.time()
    pipe = r.pipeline()

    # 月間アプリ全体 (35日で自動失効)
    app_key = f'x_api:app_posts:{month}'
    pipe.incr(app_key)
    pipe.expire(app_key, 35 * 86400)

    # 月間店舗別 (35日で自動失効)
    store_key = f'x_api:store_posts:{store_id}:{month}'
    pipe.incr(store_key)
    pipe.expire(store_key, 35 * 86400)

    # 日次スライディングウィンドウ
    pipe.zadd('x_api:daily_posts', {f'{store_id}:{now}': now})
    pipe.expire('x_api:daily_posts', 86400 + 3600)  # 25時間TTL

    pipe.execute()


def get_usage_stats():
    """現在の使用状況を取得。管理画面表示用。"""
    try:
        r = _get_redis()
    except Exception:
        return {'error': 'redis_unavailable'}

    month = _month_key()
    now = time.time()

    app_count = r.get(f'x_api:app_posts:{month}')
    app_count = int(app_count) if app_count else 0

    r.zremrangebyscore('x_api:daily_posts', '-inf', now - 86400)
    daily_count = r.zcard('x_api:daily_posts')

    usage_ratio = app_count / MONTHLY_APP_LIMIT if MONTHLY_APP_LIMIT > 0 else 0
    if usage_ratio >= ALERT_RED:
        alert_level = 'red'
    elif usage_ratio >= ALERT_YELLOW:
        alert_level = 'yellow'
    else:
        alert_level = 'green'

    return {
        'monthly_app': {'used': app_count, 'limit': MONTHLY_APP_LIMIT},
        'daily_app': {'used': daily_count, 'limit': DAILY_APP_LIMIT},
        'alert_level': alert_level,
        'usage_ratio': round(usage_ratio, 2),
    }
