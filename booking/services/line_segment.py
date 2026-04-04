"""LINEセグメント計算・配信サービス"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def recompute_segments():
    """全顧客のセグメントを再計算

    ルール:
    - vip: visit_count >= 5 or total_spent >= 30000
    - regular: visit_count >= 2 and last_visit_at within 90 days
    - dormant: last_visit_at > 90 days ago
    - new: visit_count <= 1 (default)
    """
    from booking.models.line_customer import LineCustomer

    now = timezone.now()
    cutoff_90 = now - timedelta(days=90)

    customers = LineCustomer.objects.filter(is_friend=True)
    updated = 0

    for customer in customers.iterator():
        new_segment = _compute_segment(customer, cutoff_90)
        if customer.segment != new_segment:
            LineCustomer.objects.filter(pk=customer.pk).update(segment=new_segment)
            updated += 1

    logger.info('Segment recomputation: %d customers updated', updated)
    return updated


def _compute_segment(customer, cutoff_90):
    """単一顧客のセグメントを計算"""
    if customer.visit_count >= 5 or customer.total_spent >= 30000:
        return 'vip'
    if customer.last_visit_at and customer.last_visit_at < cutoff_90:
        return 'dormant'
    if customer.visit_count >= 2:
        return 'regular'
    return 'new'


def get_customers_by_segment(segment, store_id=None):
    """セグメント別の顧客QuerySetを取得"""
    from booking.models.line_customer import LineCustomer

    qs = LineCustomer.objects.filter(segment=segment, is_friend=True)
    if store_id:
        qs = qs.filter(store_id=store_id)
    return qs


def send_segment_message(customer_ids, message_text):
    """指定顧客にメッセージを一括送信（レート制限付き）

    Args:
        customer_ids: LineCustomer IDのリスト
        message_text: 送信テキスト

    Returns:
        {'sent': int, 'failed': int}
    """
    import time
    from booking.models.line_customer import LineCustomer
    from booking.services.line_bot_service import push_text

    results = {'sent': 0, 'failed': 0}
    customers = LineCustomer.objects.filter(
        id__in=customer_ids, is_friend=True,
    ).exclude(line_user_enc='')

    for i, customer in enumerate(customers):
        ok = push_text(
            customer.line_user_enc, message_text,
            message_type='segment', customer=customer,
        )
        if ok:
            results['sent'] += 1
        else:
            results['failed'] += 1

        # レート制限: 1000msg/min ≈ 60ms/msg
        if (i + 1) % 100 == 0:
            time.sleep(6)

    logger.info(
        'Segment message sent: sent=%d, failed=%d',
        results['sent'], results['failed'],
    )
    return results
