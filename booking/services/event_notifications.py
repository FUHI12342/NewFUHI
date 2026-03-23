"""統合イベント通知ディスパッチャー

セキュリティイベント、エラー報告、IoTアラートなど重要イベント発生時に
メール通知・SHANON API連携を行う。
"""
import logging
import time

import requests
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

RATE_LIMIT_CACHE_KEY = 'event_notification_count'


def _get_notification_config():
    """SiteSettingsから通知設定を取得"""
    try:
        from booking.models import SiteSettings
        cfg = SiteSettings.load()
        return {
            'enabled': cfg.notification_enabled,
            'emails': [e.strip() for e in cfg.notification_emails.split(',') if e.strip()],
            'rate_limit': cfg.notification_rate_limit,
            'shanon_enabled': cfg.shanon_notification_enabled,
            'shanon_url': cfg.shanon_api_url,
        }
    except Exception as e:
        logger.error('通知設定の取得に失敗: %s', e)
        return None


def _check_rate_limit(rate_limit):
    """1時間あたりの通知数をチェック。制限内ならTrue"""
    count = cache.get(RATE_LIMIT_CACHE_KEY, 0)
    if count >= rate_limit:
        logger.warning('通知レート制限超過: %d/%d (1時間)', count, rate_limit)
        return False
    cache.set(RATE_LIMIT_CACHE_KEY, count + 1, timeout=3600)
    return True


def dispatch_event_notification(event_type, severity, title, detail='', admin_url=''):
    """イベント通知のメインディスパッチャー

    Args:
        event_type: イベント種別 (security_event, error_report, iot_alert, server_error)
        severity: 重要度 (critical, high, medium, low, warning, info)
        title: 通知タイトル
        detail: 詳細説明
        admin_url: 管理画面の関連URL
    """
    config = _get_notification_config()
    if not config:
        return

    # info レベルは通知スキップ
    if severity == 'info':
        logger.debug('info レベルのため通知スキップ: %s', title)
        return

    # レート制限チェック
    if not _check_rate_limit(config['rate_limit']):
        return

    # メール通知
    if config['enabled'] and config['emails']:
        _send_notification_email(config, event_type, severity, title, detail, admin_url)

    # SHANON API 通知
    if config['shanon_enabled'] and config['shanon_url']:
        _send_shanon_notification(config, event_type, severity, title, detail, admin_url)


def _send_notification_email(config, event_type, severity, title, detail, admin_url):
    """Gmail/SMTP経由でメール通知を送信"""
    severity_labels = {
        'critical': '\U0001f6a8 緊急',
        'high': '\u26a0\ufe0f 高',
        'medium': '\U0001f4cb 中',
        'low': '\u2139\ufe0f 低',
        'warning': '\u26a0\ufe0f 警告',
    }
    severity_label = severity_labels.get(severity, severity)

    subject = f'[NewFUHI] {severity_label}: {title}'

    event_labels = {
        'security_event': 'セキュリティイベント',
        'error_report': 'エラー報告',
        'iot_alert': 'IoTアラート',
        'server_error': 'サーバーエラー',
    }
    event_label = event_labels.get(event_type, event_type)

    body_parts = [
        f'イベント種別: {event_label}',
        f'重要度: {severity_label}',
        f'タイトル: {title}',
    ]
    if detail:
        body_parts.append(f'\n詳細:\n{detail}')
    if admin_url:
        site_url = getattr(settings, 'SITE_URL', 'https://timebaibai.com')
        body_parts.append(f'\n管理画面: {site_url}{admin_url}')
    body_parts.append('\n---\nこの通知はNewFUHIシステムから自動送信されています。')
    body = '\n'.join(body_parts)

    try:
        send_mail(
            subject, body,
            settings.DEFAULT_FROM_EMAIL,
            config['emails'],
            fail_silently=False,
        )
        logger.info('通知メール送信成功: %s → %s', subject, config['emails'])
    except Exception as e:
        logger.error('通知メール送信失敗: %s', e)


def _send_shanon_notification(config, event_type, severity, title, detail, admin_url, max_retries=3):
    """SHANON Health APIに通知をPOST（リトライ付き）"""
    url = f"{config['shanon_url'].rstrip('/')}/api/notifications/receive"
    payload = {
        'source': 'newfuhi',
        'event_type': event_type,
        'severity': severity,
        'title': title,
        'detail': detail,
        'admin_url': admin_url,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                logger.info('SHANON通知送信成功: %s', title)
                return True
            if resp.status_code == 429:
                logger.warning('SHANON API rate limited, retrying in %ds', 2 ** attempt)
                time.sleep(2 ** attempt)
                continue
            logger.warning('SHANON通知失敗: %d %s', resp.status_code, resp.text[:200])
            return False
        except requests.RequestException as e:
            logger.warning('SHANON通知 attempt %d failed: %s', attempt + 1, e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return False
