"""スタッフ自動評価サービス — 勤怠データから評価指標を算出"""

from datetime import date, time, timedelta
from typing import Optional

from django.db.models import Count, Sum, Q


def calculate_attendance_rate(
    staff, period_start: date, period_end: date,
) -> Optional[float]:
    """シフト割当に対する実際の出勤率を算出"""
    from booking.models import ShiftAssignment, WorkAttendance

    assignment_count = ShiftAssignment.objects.filter(
        staff=staff,
        date__gte=period_start,
        date__lte=period_end,
    ).count()

    if assignment_count == 0:
        return None

    attendance_count = WorkAttendance.objects.filter(
        staff=staff,
        date__gte=period_start,
        date__lte=period_end,
    ).exclude(clock_in__isnull=True).count()

    return round(attendance_count / assignment_count * 100, 1)


def calculate_punctuality_score(
    staff, period_start: date, period_end: date,
) -> Optional[float]:
    """定時出勤スコア (0-5) を算出。遅刻が少ないほど高スコア"""
    from booking.models import ShiftAssignment, WorkAttendance

    assignments = ShiftAssignment.objects.filter(
        staff=staff,
        date__gte=period_start,
        date__lte=period_end,
    ).values_list('date', 'start_hour')

    if not assignments:
        return None

    attendances = {
        wa.date: wa.clock_in
        for wa in WorkAttendance.objects.filter(
            staff=staff,
            date__gte=period_start,
            date__lte=period_end,
        ).exclude(clock_in__isnull=True)
    }

    scores = []
    for assign_date, start_hour in assignments:
        clock_in = attendances.get(assign_date)
        if clock_in is None:
            scores.append(0.0)
            continue

        scheduled = time(hour=int(start_hour))
        late_minutes = (
            clock_in.hour * 60 + clock_in.minute
        ) - (scheduled.hour * 60 + scheduled.minute)

        if late_minutes <= 0:
            scores.append(5.0)
        elif late_minutes <= 5:
            scores.append(4.0)
        elif late_minutes <= 15:
            scores.append(3.0)
        elif late_minutes <= 30:
            scores.append(2.0)
        else:
            scores.append(1.0)

    return round(sum(scores) / len(scores), 1) if scores else None


def calculate_total_work_hours(
    staff, period_start: date, period_end: date,
) -> Optional[float]:
    """期間内の総勤務時間を算出"""
    from booking.models import WorkAttendance

    result = WorkAttendance.objects.filter(
        staff=staff,
        date__gte=period_start,
        date__lte=period_end,
    ).aggregate(
        total=Sum('regular_minutes'),
        overtime=Sum('overtime_minutes'),
    )

    regular = result['total'] or 0
    overtime = result['overtime'] or 0
    total_minutes = regular + overtime

    if total_minutes == 0:
        return None

    return round(total_minutes / 60.0, 1)


def generate_auto_evaluation(staff, period_start: date, period_end: date):
    """自動評価を生成して返す（保存はしない）"""
    from booking.models import StaffEvaluation

    attendance_rate = calculate_attendance_rate(staff, period_start, period_end)
    punctuality = calculate_punctuality_score(staff, period_start, period_end)
    work_hours = calculate_total_work_hours(staff, period_start, period_end)

    # 総合スコア算出: 出勤率(50%) + 定時出勤(50%) → 5点満点にスケール
    score_parts = []
    if attendance_rate is not None:
        score_parts.append(min(attendance_rate / 100.0, 1.0) * 5.0 * 0.5)
    if punctuality is not None:
        score_parts.append(punctuality * 0.5)

    overall = round(sum(score_parts) / (len(score_parts) * 0.5), 1) if score_parts else None

    evaluation = StaffEvaluation(
        staff=staff,
        period_start=period_start,
        period_end=period_end,
        attendance_rate=attendance_rate,
        punctuality_score=punctuality,
        total_work_hours=work_hours,
        overall_score=overall,
        source='auto',
    )
    if overall is not None:
        evaluation.grade = evaluation.calculate_grade()

    return evaluation
