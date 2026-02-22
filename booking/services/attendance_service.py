"""
勤怠導出サービス

ShiftAssignment（確定シフト）から WorkAttendance（勤怠記録）を自動生成する。
"""
import logging
from datetime import date, time, datetime, timedelta

from django.db import transaction

logger = logging.getLogger(__name__)

# 深夜帯定義 (22:00-05:00)
LATE_NIGHT_START = 22
LATE_NIGHT_END = 5

# 法定休憩: 6h以上→60分、4.5h以上→45分
BREAK_THRESHOLD_60 = 360  # 6時間 in minutes
BREAK_THRESHOLD_45 = 270  # 4.5時間 in minutes
BREAK_60 = 60
BREAK_45 = 45

# 法定労働時間（1日8時間）
REGULAR_LIMIT_MINUTES = 480


def _calc_break_minutes(total_work_minutes: int) -> int:
    """法定休憩時間を計算する。"""
    if total_work_minutes >= BREAK_THRESHOLD_60:
        return BREAK_60
    elif total_work_minutes >= BREAK_THRESHOLD_45:
        return BREAK_45
    return 0


def _classify_work_hours(start_hour: int, end_hour: int, is_holiday: bool = False):
    """勤務時間を通常/残業/深夜/休日に分類する。

    Args:
        start_hour: 開始時間 (0-23)
        end_hour: 終了時間 (0-24, start_hourより大きい前提)
        is_holiday: 休日フラグ

    Returns:
        dict with keys: regular_minutes, overtime_minutes, late_night_minutes, holiday_minutes, break_minutes
    """
    total_minutes = (end_hour - start_hour) * 60
    break_minutes = _calc_break_minutes(total_minutes)
    net_work_minutes = total_minutes - break_minutes

    if is_holiday:
        # 休日勤務は全て休日割増
        # 深夜帯は別途深夜割増も加算
        late_night_min = 0
        for h in range(start_hour, end_hour):
            if h >= LATE_NIGHT_START or h < LATE_NIGHT_END:
                late_night_min += 60

        holiday_min = net_work_minutes - late_night_min
        return {
            'regular_minutes': 0,
            'overtime_minutes': 0,
            'late_night_minutes': late_night_min,
            'holiday_minutes': max(0, holiday_min),
            'break_minutes': break_minutes,
        }

    # 深夜時間帯の計算
    late_night_min = 0
    for h in range(start_hour, end_hour):
        if h >= LATE_NIGHT_START or h < LATE_NIGHT_END:
            late_night_min += 60

    daytime_minutes = net_work_minutes - late_night_min

    # 通常勤務 vs 残業（1日8時間超が残業）
    if daytime_minutes <= REGULAR_LIMIT_MINUTES:
        regular_minutes = daytime_minutes
        overtime_minutes = 0
    else:
        regular_minutes = REGULAR_LIMIT_MINUTES
        overtime_minutes = daytime_minutes - REGULAR_LIMIT_MINUTES

    return {
        'regular_minutes': max(0, regular_minutes),
        'overtime_minutes': max(0, overtime_minutes),
        'late_night_minutes': max(0, late_night_min),
        'holiday_minutes': 0,
        'break_minutes': break_minutes,
    }


def derive_attendance_from_shifts(store, date_from: date, date_to: date):
    """確定シフト→勤怠レコード自動生成。

    Args:
        store: Store instance
        date_from: 開始日
        date_to: 終了日

    Returns:
        int: 生成された勤怠レコード数
    """
    from booking.models import ShiftAssignment, WorkAttendance

    assignments = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=date_from,
        date__lte=date_to,
    ).select_related('staff', 'period')

    created_count = 0

    with transaction.atomic():
        for assignment in assignments:
            # 既に勤怠レコードが存在する場合はスキップ（手動修正を優先）
            existing = WorkAttendance.objects.filter(
                staff=assignment.staff,
                date=assignment.date,
            ).first()

            if existing and existing.source in ('manual', 'corrected'):
                continue

            # 休日判定（簡易: 日曜 = 休日）
            is_holiday = assignment.date.weekday() == 6  # Sunday

            hours = _classify_work_hours(
                assignment.start_hour,
                assignment.end_hour,
                is_holiday=is_holiday,
            )

            clock_in = time(assignment.start_hour, 0) if assignment.start_hour < 24 else None
            clock_out_h = assignment.end_hour if assignment.end_hour < 24 else 0
            clock_out = time(clock_out_h, 0)

            WorkAttendance.objects.update_or_create(
                staff=assignment.staff,
                date=assignment.date,
                defaults={
                    'clock_in': clock_in,
                    'clock_out': clock_out,
                    'regular_minutes': hours['regular_minutes'],
                    'overtime_minutes': hours['overtime_minutes'],
                    'late_night_minutes': hours['late_night_minutes'],
                    'holiday_minutes': hours['holiday_minutes'],
                    'break_minutes': hours['break_minutes'],
                    'source': 'shift',
                    'source_assignment': assignment,
                },
            )
            created_count += 1

    logger.info(
        "Derived %d attendance records for %s (%s ~ %s)",
        created_count, store.name, date_from, date_to,
    )
    return created_count
