from __future__ import absolute_import, unicode_literals

from celery import shared_task
import logging

from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db import models

from .models import Schedule, IoTDevice, Product
from .line_notify import send_line_notify

logger = logging.getLogger(__name__)

@shared_task
def delete_temporary_schedules():
    now = timezone.now()
    Schedule.objects.filter(
        temporary_booked_at__lt=now - timezone.timedelta(minutes=10),
        is_temporary=True,
        is_cancelled=False,
    ).delete()


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
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [device.alert_email], fail_silently=True)
        except Exception as e:
            logger.error('ガスアラートメール送信失敗: %s', e)


@shared_task
def check_low_stock_and_notify():
    """
    在庫閾値チェックとLINE通知。
    連続通知を避けるため、24h以内の再通知はスキップ。
    """
    now = timezone.now()
    cutoff = now - timezone.timedelta(hours=24)

    # 閾値設定済み + 在庫割れ + 通知未済 or 24h以上経過
    products = Product.objects.filter(
        low_stock_threshold__isnull=False,
        stock__lte=models.F('low_stock_threshold')
    ).exclude(
        models.Q(last_low_stock_notified_at__isnull=False) &
        models.Q(last_low_stock_notified_at__gt=cutoff)
    )

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