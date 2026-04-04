"""空き枠検索サービス（共通化）"""
import datetime
import logging

from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_available_slots(staff, date, store=None):
    """指定スタッフ・日付の空き枠リストを返す

    Args:
        staff: Staff instance
        date: datetime.date
        store: Store instance (空の場合はスタッフの主店舗)

    Returns:
        list of dict: [{'hour': int, 'minute': int, 'total_minutes': int,
                        'label': str}, ...]
    """
    from booking.models import Schedule
    from booking.views import get_time_slots

    target_store = store or staff.store
    time_slots, open_h, close_h, duration = get_time_slots(target_store)

    # その日の全予約を取得
    day_start = datetime.datetime.combine(date, datetime.time(hour=open_h))
    day_end = datetime.datetime.combine(date, datetime.time(hour=close_h))

    booked_labels = set()
    for schedule in Schedule.objects.filter(
        staff=staff,
        is_cancelled=False,
    ).exclude(Q(start__gte=day_end) | Q(end__lte=day_start)):
        local_dt = timezone.localtime(schedule.start)
        if local_dt.date() == date:
            booked_labels.add(f"{local_dt.hour}:{local_dt.minute:02d}")

    # 過去の時刻を除外
    now = timezone.localtime(timezone.now())
    available = []
    for slot in time_slots:
        if slot['label'] in booked_labels:
            continue
        # 当日の場合、過去のスロットは除外
        if date == now.date():
            slot_time = datetime.time(hour=slot['hour'], minute=slot['minute'])
            if slot_time <= now.time():
                continue
        available.append(slot)

    return available


def get_available_dates(staff, store=None, days_ahead=14):
    """指定スタッフの空きがある日付リストを返す

    Args:
        staff: Staff instance
        store: Store instance
        days_ahead: 何日先まで検索するか

    Returns:
        list of datetime.date
    """
    today = datetime.date.today()
    available_dates = []

    for i in range(1, days_ahead + 1):
        date = today + datetime.timedelta(days=i)
        slots = get_available_slots(staff, date, store)
        if slots:
            available_dates.append(date)

    return available_dates
