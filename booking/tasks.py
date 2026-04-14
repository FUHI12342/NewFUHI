from __future__ import absolute_import, unicode_literals

from celery import shared_task
import logging

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models

from .models import Schedule, IoTDevice, IoTEvent, Product, Property, PropertyDevice, PropertyAlert
from .line_notify import send_line_notify

logger = logging.getLogger(__name__)

@shared_task
def delete_temporary_schedules():
    """20分経過した仮予約を自動キャンセル"""
    now = timezone.now()
    expired = Schedule.objects.filter(
        temporary_booked_at__lt=now - timezone.timedelta(minutes=20),
        is_temporary=True,
        is_cancelled=False,
    )
    count = expired.update(is_cancelled=True)
    if count:
        logger.info('仮予約 %d件を自動キャンセルしました', count)


@shared_task
def trigger_gas_alert(device_id, mq9_value, event_id):
    try:
        device = IoTDevice.objects.get(id=device_id)
    except IoTDevice.DoesNotExist:
        return

    if device.alert_email:
        subject = f'[Gas Alert] {device.name} MQ-9 高濃度検知'
        message = f'デバイス: {device.name}\n店舗: {device.store.name}\nMQ-9値: {mq9_value}\n'
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [device.alert_email], fail_silently=False)
        except Exception as e:
            logger.error('ガスアラートメール送信失敗: %s', e)


@shared_task
def check_low_stock_and_notify():
    """
    在庫閾値チェックとLINE通知。
    連続通知を避けるため、4h以内の再通知はスキップ。
    """
    now = timezone.now()
    cutoff = now - timezone.timedelta(hours=4)

    # 閾値設定済み + 在庫割れ + 通知未済 or 4h以上経過
    products = Product.objects.filter(
        low_stock_threshold__isnull=False,
        stock__lte=models.F('low_stock_threshold')
    ).exclude(
        models.Q(last_low_stock_notified_at__isnull=False) &
        models.Q(last_low_stock_notified_at__gt=cutoff)
    ).select_related('store')

    notified_count = 0
    for product in products:
        message = f'[在庫アラート] {product.store.name} - {product.sku} {product.name}\n在庫: {product.stock} (閾値: {product.low_stock_threshold})'
        if send_line_notify(message):
            product.last_low_stock_notified_at = now
            product.save(update_fields=['last_low_stock_notified_at'])
            notified_count += 1
            logger.info('Low stock notification sent for %s', product.sku)
        else:
            logger.error('Failed to send low stock notification for %s', product.sku)

    logger.info('Low stock check completed: %d notifications sent', notified_count)


@shared_task
def check_property_alerts():
    """
    物件アラート検知（5分ごと実行）。
    - ガス漏れ: MQ-9がthreshold超過（直近5分）→ critical
    - 長期不在: PIR未検知3日以上 → warning
    - デバイスオフライン: last_seen_at 30分超過 → info
    - 重複アラート防止（未解決の同種アラートがあればスキップ）
    """
    now = timezone.now()
    created = 0

    # N+1 対策: prefetch_related で一括取得
    props = Property.objects.filter(is_active=True).prefetch_related(
        models.Prefetch(
            'propertydevice_set',
            queryset=PropertyDevice.objects.select_related('device'),
        )
    )

    # 全アクティブデバイスIDを収集して一括クエリ
    all_pds = []
    for prop in props:
        all_pds.extend(
            (prop, pd) for pd in prop.propertydevice_set.all() if pd.device.is_active
        )

    if not all_pds:
        logger.info('Property alert check completed: 0 new alerts created')
        return

    active_device_ids = [pd.device_id for _, pd in all_pds]

    # 直近5分のガスイベント（threshold超過デバイス一括取得）
    five_min_ago = now - timezone.timedelta(minutes=5)
    gas_device_ids = set(
        IoTEvent.objects.filter(
            device_id__in=active_device_ids,
            created_at__gte=five_min_ago,
        ).exclude(mq9_value__isnull=True).values_list('device_id', flat=True).distinct()
    )

    # 直近PIRイベント（デバイスごとに最新1件）
    from django.db.models import Max
    last_pir_map = dict(
        IoTEvent.objects.filter(
            device_id__in=active_device_ids,
            pir_triggered=True,
        ).values('device_id').annotate(last_at=Max('created_at')).values_list('device_id', 'last_at')
    )

    # 未解決アラート（一括取得）
    open_alerts = set(
        PropertyAlert.objects.filter(
            property__in=[p for p, _ in all_pds],
            device_id__in=active_device_ids,
            is_resolved=False,
        ).values_list('property_id', 'device_id', 'alert_type')
    )

    for prop, pd in all_pds:
        device = pd.device

        # --- Gas leak detection ---
        if device.mq9_threshold and device.id in gas_device_ids:
            # 個別にthreshold超過を確認
            has_high = IoTEvent.objects.filter(
                device=device,
                created_at__gte=five_min_ago,
                mq9_value__gt=device.mq9_threshold,
            ).exists()
            if has_high and (prop.id, device.id, 'gas_leak') not in open_alerts:
                PropertyAlert.objects.create(
                    property=prop, device=device,
                    alert_type='gas_leak', severity='critical',
                    message=f'{device.name} ({pd.location_label}): MQ-9がthreshold({device.mq9_threshold})を超過しました',
                )
                created += 1
                try:
                    send_event_notification.delay(
                        'iot_alert', 'critical',
                        f'ガス漏れ検知: {device.name}',
                        f'{device.name} ({pd.location_label}): MQ-9がthreshold({device.mq9_threshold})を超過',
                        '',
                    )
                except Exception as exc:
                    logger.warning('Gas alert notification failed: %s', exc)

        # --- No motion detection (3 days) ---
        last_pir_at = last_pir_map.get(device.id)
        if last_pir_at and (now - last_pir_at).days >= 3:
            if (prop.id, device.id, 'no_motion') not in open_alerts:
                PropertyAlert.objects.create(
                    property=prop, device=device,
                    alert_type='no_motion', severity='warning',
                    message=f'{device.name} ({pd.location_label}): 3日以上動体未検知',
                )
                created += 1
                try:
                    send_event_notification.delay(
                        'iot_alert', 'warning',
                        f'長期不在検知: {device.name}',
                        f'{device.name} ({pd.location_label}): 3日以上動体未検知',
                        '',
                    )
                except Exception as exc:
                    logger.warning('No-motion alert notification failed: %s', exc)

        # --- Device offline (30 min) ---
        if device.last_seen_at and (now - device.last_seen_at).total_seconds() > 1800:
            if (prop.id, device.id, 'device_offline') not in open_alerts:
                PropertyAlert.objects.create(
                    property=prop, device=device,
                    alert_type='device_offline', severity='info',
                    message=f'{device.name} ({pd.location_label}): 30分以上通信なし',
                )
                created += 1

    logger.info('Property alert check completed: %d new alerts created', created)


@shared_task
def run_security_audit():
    """セキュリティ監査を実行（Celery Beat から毎日 03:00）"""
    from django.core.management import call_command
    call_command('security_audit')
    logger.info('Security audit completed')


@shared_task
def cleanup_security_logs():
    """90日超のセキュリティログを削除（Celery Beat から毎週日曜 04:00）"""
    from django.core.management import call_command
    call_command('cleanup_security_logs', '--days', '90')
    logger.info('Security log cleanup completed')


@shared_task
def check_aws_costs():
    """AWSコストチェックを実行（Celery Beat から毎日 06:00）"""
    from django.core.management import call_command
    call_command('check_aws_costs', '--threshold', '50')
    logger.info('AWS cost check completed')


@shared_task
def aggregate_visitor_data():
    """毎時実行: PIR IoTEvent → VisitorCount 集計"""
    from booking.models import Store
    from booking.services.visitor_analytics import aggregate_visitor_counts
    from datetime import date

    today = date.today()
    total = 0
    stores = list(Store.objects.only('id', 'name'))
    for store in stores:
        count = aggregate_visitor_counts(store, today, today)
        total += count
    logger.info('Visitor data aggregation completed: %d records for %d stores', total, len(stores))


@shared_task
def send_event_notification(event_type, severity, title, detail='', admin_url=''):
    """イベント通知送信（Celeryワーカーで非同期実行）"""
    from booking.services.event_notifications import dispatch_event_notification
    dispatch_event_notification(event_type, severity, title, detail, admin_url)


# ==============================
# SNS自動投稿タスク
# ==============================

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def task_post_to_x(self, store_id, trigger_type, context_json):
    """X API投稿タスク。専用キュー x_api で単一ワーカー実行。"""
    from booking.services.post_dispatcher import dispatch_post
    try:
        dispatch_post(store_id, trigger_type, context_json)
    except Exception as exc:
        logger.error("task_post_to_x failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def task_post_shift_published(period_id):
    """シフト公開時のSNS投稿をキューイング"""
    from booking.models import ShiftPeriod
    try:
        period = ShiftPeriod.objects.select_related('store').get(id=period_id)
    except ShiftPeriod.DoesNotExist:
        logger.error("ShiftPeriod not found: %s", period_id)
        return
    task_post_to_x.apply_async(
        args=[period.store_id, 'shift_publish', {'period_id': period_id}],
        queue='x_api',
    )


@shared_task
def task_post_daily_staff():
    """毎日09:30: 各店舗の本日スタッフを投稿"""
    from booking.models import SocialAccount
    for account in SocialAccount.objects.filter(is_active=True, platform='x'):
        task_post_to_x.apply_async(
            args=[account.store_id, 'daily_staff', {}],
            queue='x_api',
        )


@shared_task
def task_post_weekly_schedule():
    """毎週月曜10:00: 週間スケジュールを投稿"""
    from booking.models import SocialAccount
    for account in SocialAccount.objects.filter(is_active=True, platform='x'):
        task_post_to_x.apply_async(
            args=[account.store_id, 'weekly_schedule', {}],
            queue='x_api',
        )


@shared_task
def task_refresh_social_tokens():
    """毎日03:30: 期限が近いトークンをリフレッシュ"""
    from booking.models import SocialAccount
    from booking.services.x_posting_service import refresh_x_token
    threshold = timezone.now() + timezone.timedelta(hours=6)
    for account in SocialAccount.objects.filter(
        is_active=True, token_expires_at__lte=threshold,
    ):
        try:
            refresh_x_token(account)
        except Exception as e:
            logger.warning("Token refresh failed for store %s: %s", account.store_id, e)


@shared_task
def task_generate_daily_drafts():
    """毎日08:00: 各店舗の下書き自動生成"""
    from booking.models import Store, SocialAccount
    from booking.services.sns_draft_service import generate_daily_draft
    from booking.services.sns_evaluation_service import evaluate_draft_quality

    # アクティブな SocialAccount がある店舗のみ対象
    store_ids = SocialAccount.objects.filter(
        is_active=True,
    ).values_list('store_id', flat=True).distinct()

    for store in Store.objects.filter(id__in=store_ids):
        try:
            draft = generate_daily_draft(store)
            if draft:
                evaluate_draft_quality(draft)
                logger.info("Daily draft generated for store %s (score=%.2f)", store.name, draft.quality_score or 0)
        except Exception as e:
            logger.error("Daily draft generation failed for store %s: %s", store.name, e)


@shared_task
def task_check_scheduled_posts():
    """5分ごと: 予約投稿の時刻チェック → 投稿実行"""
    from booking.models import DraftPost
    from booking.services.post_dispatcher import dispatch_post

    now = timezone.now()
    scheduled_drafts = DraftPost.objects.filter(
        status='scheduled',
        scheduled_at__lte=now,
    ).select_related('store')

    for draft in scheduled_drafts:
        try:
            context_json = {'content': draft.content, 'draft_id': draft.pk}
            dispatch_post(draft.store_id, 'manual', context_json)
            draft.status = 'posted'
            draft.posted_at = now
            draft.save(update_fields=['status', 'posted_at', 'updated_at'])
            logger.info("Scheduled post dispatched: draft_id=%d", draft.pk)
        except Exception as e:
            logger.error("Scheduled post failed for draft %d: %s", draft.pk, e)


@shared_task
def send_day_before_reminders():
    """前日リマインダー送信（毎日18:00 JST）"""
    from booking.models import SiteSettings
    if not SiteSettings.load().line_reminder_enabled:
        return
    from booking.services.line_reminder import send_day_before_reminders as _send
    _send()


@shared_task
def send_same_day_reminders():
    """当日リマインダー送信（30分ごと）"""
    from booking.models import SiteSettings
    if not SiteSettings.load().line_reminder_enabled:
        return
    from booking.services.line_reminder import send_same_day_reminders as _send
    _send()


@shared_task
def recompute_customer_segments():
    """顧客セグメント日次再計算"""
    from booking.models import SiteSettings
    if not SiteSettings.load().line_segment_enabled:
        return
    from booking.services.line_segment import recompute_segments
    recompute_segments()


@shared_task
def task_send_segment_message(customer_ids, message_text):
    """セグメント配信タスク"""
    from booking.models import SiteSettings
    if not SiteSettings.load().line_segment_enabled:
        return
    from booking.services.line_segment import send_segment_message
    send_segment_message(customer_ids, message_text)


@shared_task
def generate_live_demo_data_task():
    """30分毎: デモモード有効時に当日デモデータを生成"""
    from booking.models import SiteSettings
    if not SiteSettings.load().demo_mode_enabled:
        return
    from django.core.management import call_command
    call_command('generate_live_demo_data')
    logger.info('Live demo data generation completed')


@shared_task
def run_scheduled_backup():
    """毎分実行: BackupConfigの間隔設定に基づきバックアップ実行判定"""
    from booking.models import BackupConfig, BackupHistory

    config = BackupConfig.load()
    if not config.is_active or config.interval == 'off':
        return

    intervals = {'minute': 60, 'hourly': 3600, 'daily': 86400}
    interval_seconds = intervals.get(config.interval, 86400)

    last_success = (
        BackupHistory.objects
        .filter(status='success')
        .order_by('-started_at')
        .first()
    )

    if last_success:
        elapsed = (timezone.now() - last_success.started_at).total_seconds()
        if elapsed < interval_seconds * 0.9:
            return  # まだ早い

    from booking.services.backup_service import create_backup
    create_backup(trigger='scheduled')
    logger.info('Scheduled backup completed')