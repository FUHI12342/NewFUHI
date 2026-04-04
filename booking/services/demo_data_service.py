"""Demo data service — controls demo data visibility in dashboards."""
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_KEY = 'demo_mode_enabled'
CACHE_TTL = 60  # 60秒キャッシュ


def is_demo_mode_active():
    """SiteSettings.demo_mode_enabled を60秒キャッシュで返す。"""
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached
    from booking.models import SiteSettings
    enabled = SiteSettings.load().demo_mode_enabled
    cache.set(CACHE_KEY, enabled, CACHE_TTL)
    return enabled


def get_demo_exclusion(prefix=''):
    """デモモードOFF時にis_demo=Trueを除外するフィルタkwargsを返す。

    デモモードON → {} (全データ表示)
    デモモードOFF → {'{prefix}is_demo': False} (デモデータ除外)
    """
    if is_demo_mode_active():
        return {}
    key = f'{prefix}is_demo' if prefix else 'is_demo'
    return {key: False}


def invalidate_demo_mode_cache():
    """管理画面でデモモード変更時にキャッシュ無効化。"""
    cache.delete(CACHE_KEY)
