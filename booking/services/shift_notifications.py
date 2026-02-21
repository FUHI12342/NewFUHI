"""シフト関連 LINE/メール通知サービス"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from booking.line_notify import send_line_notify

logger = logging.getLogger(__name__)


def notify_shift_period_open(period):
    """シフト募集開始通知 (LINE + メール)"""
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')
    deadline_str = timezone.localtime(period.deadline).strftime('%Y/%m/%d %H:%M')

    message = (
        f"【シフト募集開始】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"申請締切: {deadline_str}\n"
        f"管理画面からシフト希望を入力してください。"
    )

    # LINE通知
    try:
        send_line_notify(message)
    except Exception as e:
        logger.warning("LINE notify failed for shift period open: %s", e)

    # メール通知（スタッフ全員）
    from booking.models import Staff
    staff_emails = list(
        Staff.objects.filter(store=store)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )
    if staff_emails:
        try:
            send_mail(
                subject=f'シフト募集開始: {month_str}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=staff_emails,
                fail_silently=True,
            )
        except Exception as e:
            logger.warning("Email notify failed for shift period open: %s", e)


def notify_shift_approved(period):
    """シフト承認完了通知 (LINE + メール)"""
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')

    message = (
        f"【シフト確定】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"シフトが確定しました。管理画面でご確認ください。"
    )

    try:
        send_line_notify(message)
    except Exception as e:
        logger.warning("LINE notify failed for shift approved: %s", e)

    from booking.models import Staff
    staff_emails = list(
        Staff.objects.filter(store=store)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )
    if staff_emails:
        try:
            send_mail(
                subject=f'シフト確定: {month_str}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=staff_emails,
                fail_silently=True,
            )
        except Exception as e:
            logger.warning("Email notify failed for shift approved: %s", e)


def notify_booking_confirmed(schedule):
    """予約確定通知 (スタッフ向け LINE)"""
    staff = schedule.staff
    local_time = timezone.localtime(schedule.start).strftime('%Y/%m/%d %H:%M')

    message = (
        f"【予約確定】\n"
        f"日時: {local_time}\n"
        f"お客様: {schedule.customer_name or '未設定'}\n"
        f"料金: {schedule.price}円"
    )

    try:
        send_line_notify(message)
    except Exception as e:
        logger.warning("LINE notify failed for booking confirmed: %s", e)
