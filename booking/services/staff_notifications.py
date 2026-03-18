"""スタッフ個別LINE通知サービス

アカウントごとの通知設定を尊重し、LineBotApi.push_message で個別配信する。
既存の send_line_notify() (ブロードキャスト) を置き換える用途。
"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)

# 通知種別 → Staff フィールド名のマッピング
NOTIFICATION_PREF_FIELDS = {
    'booking': 'notify_booking',
    'shift': 'notify_shift',
    'business': 'notify_business',
}


def _push_line_message(line_id: str, message: str, max_retries: int = 3) -> bool:
    """LineBotApi.push_message をリトライ付きで送信（内部ヘルパー）"""
    from linebot import LineBotApi
    from linebot.models import TextSendMessage

    access_token = getattr(settings, 'LINE_ACCESS_TOKEN', None)
    if not access_token:
        logger.warning("LINE_ACCESS_TOKEN is not set")
        return False

    for attempt in range(max_retries):
        try:
            bot = LineBotApi(access_token)
            bot.push_message(line_id, TextSendMessage(text=message))
            return True
        except Exception as e:
            logger.warning(
                "LINE push attempt %d/%d failed (line_id=%s): %s",
                attempt + 1, max_retries, line_id[:8], e,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return False


def send_staff_line(staff, message: str, notification_type: str = 'business') -> bool:
    """個別スタッフにLINE通知を送信（通知設定を尊重）

    Args:
        staff: Staff インスタンス
        message: 送信メッセージ
        notification_type: 'booking' | 'shift' | 'business'

    Returns:
        True=送信成功, False=スキップまたは失敗
    """
    pref_field = NOTIFICATION_PREF_FIELDS.get(notification_type)
    if pref_field is None:
        logger.warning("Unknown notification_type: %s", notification_type)
        return False

    if not getattr(staff, pref_field, False):
        logger.debug(
            "Notification skipped: %s has %s=False", staff.name, pref_field,
        )
        return False

    if not staff.line_id:
        logger.debug("Notification skipped: %s has no line_id", staff.name)
        return False

    return _push_line_message(staff.line_id, message)


def notify_booking_to_staff(schedule) -> bool:
    """予約確定時にスタッフへ通知"""
    from django.utils import timezone

    staff = schedule.staff
    local_time = timezone.localtime(schedule.start).strftime('%Y/%m/%d %H:%M')
    store_name = staff.store.name if hasattr(staff, 'store') and staff.store else ''

    message = (
        f"【予約確定】\n"
        f"日時: {local_time}\n"
        f"お客様: {schedule.customer_name or '未設定'}\n"
        f"店舗: {store_name}\n"
        f"料金: {schedule.price}円\n"
        f"予約番号: {schedule.reservation_number}"
    )
    return send_staff_line(staff, message, notification_type='booking')


def notify_shift_published(period) -> dict:
    """シフト公開時に対象スタッフ全員に個別通知

    Returns:
        {'sent': int, 'skipped': int, 'failed': int}
    """
    store = period.store
    month_str = period.year_month.strftime('%Y年%m月')

    message = (
        f"【シフト確定】\n"
        f"店舗: {store.name}\n"
        f"対象月: {month_str}\n"
        f"シフトが確定しました。管理画面でご確認ください。"
    )

    results = {'sent': 0, 'skipped': 0, 'failed': 0}

    staff_ids_seen = set()
    for assignment in period.assignments.select_related('staff').all():
        staff = assignment.staff
        if staff.id in staff_ids_seen:
            continue
        staff_ids_seen.add(staff.id)

        ok = send_staff_line(staff, message, notification_type='shift')
        if ok:
            results['sent'] += 1
        elif not staff.line_id or not staff.notify_shift:
            results['skipped'] += 1
        else:
            results['failed'] += 1

    return results


def send_business_message(staff_queryset, message: str, sender_name: str = '') -> dict:
    """業務連絡を対象スタッフに一斉送信

    Args:
        staff_queryset: Staff の QuerySet またはリスト
        message: 送信メッセージ本文
        sender_name: 送信者名（メッセージに付加）

    Returns:
        {'sent': int, 'skipped': int, 'failed': int}
    """
    results = {'sent': 0, 'skipped': 0, 'failed': 0}

    full_message = f"【業務連絡】\n"
    if sender_name:
        full_message += f"送信者: {sender_name}\n"
    full_message += f"\n{message}"

    for staff in staff_queryset:
        ok = send_staff_line(staff, full_message, notification_type='business')
        if ok:
            results['sent'] += 1
        elif not staff.line_id or not staff.notify_business:
            results['skipped'] += 1
        else:
            results['failed'] += 1

    return results
