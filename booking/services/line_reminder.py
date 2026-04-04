"""LINE予約リマインダーサービス"""
import logging
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def send_day_before_reminders():
    """翌日の予約に前日リマインダーを送信（毎日18:00 JST実行）

    対象: 明日の予約で、reminder_sent_day_before=False, is_cancelled=False, is_temporary=False
    """
    from booking.models import Schedule
    from booking.models.line_customer import LineCustomer
    from booking.services.line_bot_service import push_text

    now = timezone.now()
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    schedules = (
        Schedule.objects
        .filter(
            start__gte=tomorrow_start,
            start__lt=tomorrow_end,
            is_cancelled=False,
            is_temporary=False,
            reminder_sent_day_before=False,
            line_user_enc__isnull=False,
        )
        .exclude(line_user_enc='')
        .select_related('staff', 'store')
    )

    sent_count = 0
    for schedule in schedules:
        local_start = timezone.localtime(schedule.start)
        store_name = schedule.store.name if schedule.store else ''
        message = (
            f'【明日のご予約リマインダー】\n\n'
            f'日時: {local_start:%Y/%m/%d %H:%M}\n'
            f'担当: {schedule.staff.name}\n'
            f'店舗: {store_name}\n'
            f'予約番号: {schedule.reservation_number}\n\n'
            f'ご来店をお待ちしております。'
        )

        # LineCustomerを紐づけてログに記録
        customer = None
        if schedule.line_user_hash:
            customer = LineCustomer.objects.filter(
                line_user_hash=schedule.line_user_hash,
            ).first()

        ok = push_text(
            schedule.line_user_enc, message,
            message_type='reminder', customer=customer,
        )
        if ok:
            Schedule.objects.filter(pk=schedule.pk).update(reminder_sent_day_before=True)
            sent_count += 1

    logger.info('Day-before reminders sent: %d', sent_count)
    return sent_count


def send_same_day_reminders():
    """当日の予約に2時間前リマインダーを送信（30分ごと実行）

    対象: 2時間以内の予約で、reminder_sent_same_day=False, is_cancelled=False, is_temporary=False
    """
    from booking.models import Schedule
    from booking.models.line_customer import LineCustomer
    from booking.services.line_bot_service import push_text

    now = timezone.now()
    two_hours_later = now + timedelta(hours=2)

    schedules = (
        Schedule.objects
        .filter(
            start__gte=now,
            start__lte=two_hours_later,
            is_cancelled=False,
            is_temporary=False,
            reminder_sent_same_day=False,
            line_user_enc__isnull=False,
        )
        .exclude(line_user_enc='')
        .select_related('staff', 'store')
    )

    sent_count = 0
    for schedule in schedules:
        local_start = timezone.localtime(schedule.start)
        store_name = schedule.store.name if schedule.store else ''
        message = (
            f'【本日のご予約リマインダー】\n\n'
            f'日時: {local_start:%H:%M}\n'
            f'担当: {schedule.staff.name}\n'
            f'店舗: {store_name}\n\n'
            f'まもなくお時間です。ご来店をお待ちしております。'
        )

        customer = None
        if schedule.line_user_hash:
            customer = LineCustomer.objects.filter(
                line_user_hash=schedule.line_user_hash,
            ).first()

        ok = push_text(
            schedule.line_user_enc, message,
            message_type='reminder', customer=customer,
        )
        if ok:
            Schedule.objects.filter(pk=schedule.pk).update(reminder_sent_same_day=True)
            sent_count += 1

    logger.info('Same-day reminders sent: %d', sent_count)
    return sent_count
