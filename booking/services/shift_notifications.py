"""シフト関連 LINE/メール通知サービス

LINE通知: send_staff_line() による個別Push（通知設定を尊重）
メール通知: send_mail() による一括送信（従来通り）
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from booking.services.staff_notifications import send_staff_line

logger = logging.getLogger(__name__)


def _send_email_to_store_staff(store, subject, message):
    """店舗スタッフ全員にメール送信（内部ヘルパー）"""
    from booking.models import Staff
    staff_emails = list(
        Staff.objects.filter(store=store)
        .exclude(user__email='')
        .values_list('user__email', flat=True)
    )
    if not staff_emails:
        return
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=staff_emails,
            fail_silently=True,
        )
    except Exception as e:
        logger.warning("Email notify failed: %s", e)


def _send_line_to_store_staff(store, message, notification_type='shift'):
    """店舗スタッフ全員にLINE個別Push"""
    from booking.models import Staff
    for staff in Staff.objects.filter(store=store).select_related('user'):
        try:
            send_staff_line(staff, message, notification_type=notification_type)
        except Exception as e:
            logger.warning("LINE push failed for %s: %s", staff.name, e)


def notify_shift_period_open(period):
    """シフト募集開始通知 (LINE個別Push + メール)"""
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')
    deadline_str = (
        timezone.localtime(period.deadline).strftime('%Y/%m/%d %H:%M')
        if period.deadline else '未設定'
    )

    message = (
        f"【シフト募集開始】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"申請締切: {deadline_str}\n"
        f"管理画面からシフト希望を入力してください。"
    )

    _send_line_to_store_staff(store, message, notification_type='shift')
    _send_email_to_store_staff(store, f'シフト募集開始: {month_str}', message)


def notify_shift_approved(period):
    """シフト承認完了通知 (LINE個別Push + メール)"""
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')

    message = (
        f"【シフト確定】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"シフトが確定しました。管理画面でご確認ください。"
    )

    _send_line_to_store_staff(store, message, notification_type='shift')
    _send_email_to_store_staff(store, f'シフト確定: {month_str}', message)


def notify_shift_revoked(period, reason=''):
    """シフト撤回通知 (LINE個別Push + メール)"""
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')

    message = (
        f"【シフト撤回】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"公開済みシフトが撤回されました。\n"
        f"理由: {reason}\n"
        f"再度公開されるまでお待ちください。"
    )

    _send_line_to_store_staff(store, message, notification_type='shift')
    _send_email_to_store_staff(store, f'シフト撤回: {month_str}', message)


def notify_shift_revised(assignment, changes):
    """個別シフト修正通知 (LINE個別Push + メール)"""
    staff = assignment.staff
    store = assignment.period.store
    date_str = assignment.date.strftime('%Y/%m/%d')

    old_start = changes.get('old_start_hour', assignment.start_hour)
    old_end = changes.get('old_end_hour', assignment.end_hour)
    new_start = assignment.start_hour
    new_end = assignment.end_hour

    message = (
        f"【シフト変更】\n"
        f"店舗: {store.name}\n"
        f"{staff.name}さんの {date_str} のシフトが変更されました。\n"
        f"変更前: {old_start}:00-{old_end}:00\n"
        f"変更後: {new_start}:00-{new_end}:00"
    )

    try:
        send_staff_line(staff, message, notification_type='shift')
    except Exception as e:
        logger.warning("LINE push failed for shift revised: %s", e)

    if hasattr(staff, 'user') and staff.user and staff.user.email:
        try:
            send_mail(
                subject=f'シフト変更: {date_str}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[staff.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.warning("Email notify failed for shift revised: %s", e)


def notify_booking_confirmed(schedule):
    """予約確定通知 (スタッフ向け LINE個別Push)"""
    from booking.services.staff_notifications import notify_booking_to_staff
    return notify_booking_to_staff(schedule)


# ==============================
# イレギュラー対策通知
# ==============================

def notify_swap_request(swap_req):
    """交代・欠勤申請通知（管理者 + 対象スタッフへ）"""
    from booking.models import Staff
    assignment = swap_req.assignment
    store = assignment.period.store
    date_str = assignment.date.strftime('%Y/%m/%d')
    type_display = swap_req.get_request_type_display()

    # 管理者への通知
    manager_msg = (
        f"【{type_display}申請】\n"
        f"店舗: {store.name}\n"
        f"申請者: {swap_req.requested_by.name}\n"
        f"日時: {date_str} {assignment.start_hour}:00-{assignment.end_hour}:00\n"
        f"理由: {swap_req.reason}\n"
        f"管理画面から承認/却下してください。"
    )
    managers = Staff.objects.filter(
        store=store, is_store_manager=True,
    ).select_related('user')
    for mgr in managers:
        try:
            send_staff_line(mgr, manager_msg, notification_type='shift')
        except Exception as e:
            logger.warning("LINE push failed for swap request to manager: %s", e)

    # 交代先スタッフへの通知
    if swap_req.cover_staff:
        cover_msg = (
            f"【シフト交代依頼】\n"
            f"{swap_req.requested_by.name}さんから交代依頼があります。\n"
            f"日時: {date_str} {assignment.start_hour}:00-{assignment.end_hour}:00\n"
            f"理由: {swap_req.reason}\n"
            f"管理者の承認後に確定します。"
        )
        try:
            send_staff_line(swap_req.cover_staff, cover_msg, notification_type='shift')
        except Exception as e:
            logger.warning("LINE push failed for swap cover staff: %s", e)


def notify_swap_approved(swap_req):
    """交代・欠勤申請の承認/却下通知"""
    assignment = swap_req.assignment
    store = assignment.period.store
    date_str = assignment.date.strftime('%Y/%m/%d')
    status_display = swap_req.get_status_display()
    type_display = swap_req.get_request_type_display()

    # 申請者への通知
    requester_msg = (
        f"【{type_display}申請 {status_display}】\n"
        f"店舗: {store.name}\n"
        f"日時: {date_str} {assignment.start_hour}:00-{assignment.end_hour}:00\n"
        f"あなたの{type_display}申請が{status_display}されました。"
    )
    try:
        send_staff_line(swap_req.requested_by, requester_msg, notification_type='shift')
    except Exception as e:
        logger.warning("LINE push failed for swap approval to requester: %s", e)

    # 交代先スタッフへの通知
    if swap_req.cover_staff:
        cover_msg = (
            f"【シフト交代 {status_display}】\n"
            f"{date_str} {assignment.start_hour}:00-{assignment.end_hour}:00\n"
            f"交代が{status_display}されました。"
        )
        try:
            send_staff_line(swap_req.cover_staff, cover_msg, notification_type='shift')
        except Exception as e:
            logger.warning("LINE push failed for swap approval to cover: %s", e)


def notify_emergency_cover(vacancy):
    """緊急カバー募集通知（全スタッフへ）"""
    store = vacancy.store
    date_str = vacancy.date.strftime('%Y/%m/%d')
    type_display = dict(vacancy._meta.get_field('staff_type').choices).get(
        vacancy.staff_type, vacancy.staff_type,
    )

    message = (
        f"【緊急カバー募集】\n"
        f"店舗: {store.name}\n"
        f"日時: {date_str} {vacancy.start_hour}:00〜{vacancy.end_hour}:00\n"
        f"種別: {type_display}\n"
        f"不足: {vacancy.shortage}名\n"
        f"対応可能な方はシフト管理画面から応募してください。"
    )

    from booking.models import Staff
    target_staff = Staff.objects.filter(
        store=store, staff_type=vacancy.staff_type,
    ).select_related('user')
    for s in target_staff:
        try:
            send_staff_line(s, message, notification_type='shift')
        except Exception as e:
            logger.warning("LINE push for emergency cover failed for %s: %s", s.name, e)
