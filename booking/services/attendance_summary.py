"""スタッフ勤務実績サマリー計算"""
from __future__ import annotations

import calendar
import logging
from datetime import date
from typing import Optional

from django.db.models import Count, Sum

from booking.models import Staff, WorkAttendance

logger = logging.getLogger(__name__)


def _month_date_range(year: int, month: int) -> tuple:
    """Return (first_day, last_day) for the given year/month."""
    first = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    return first, last


def get_monthly_summary(
    store,
    year: int,
    month: int,
    staff_id: Optional[int] = None,
) -> list:
    """
    Return a list of dicts (one per staff) with monthly work totals.
    Never mutates any argument.
    """
    first, last = _month_date_range(year, month)

    staff_qs = Staff.objects.select_related('store')
    if store:
        staff_qs = staff_qs.filter(store=store)
    if staff_id:
        staff_qs = staff_qs.filter(id=staff_id)

    attendance_qs = WorkAttendance.objects.filter(
        date__gte=first, date__lte=last,
    )
    if store:
        attendance_qs = attendance_qs.filter(staff__store=store)
    if staff_id:
        attendance_qs = attendance_qs.filter(staff_id=staff_id)

    aggregated = (
        attendance_qs
        .values('staff_id')
        .annotate(
            attendance_days=Count('id'),
            total_regular=Sum('regular_minutes'),
            total_overtime=Sum('overtime_minutes'),
            total_late_night=Sum('late_night_minutes'),
            total_holiday=Sum('holiday_minutes'),
            total_break=Sum('break_minutes'),
        )
    )
    agg_map = {row['staff_id']: row for row in aggregated}

    result = []
    for s in staff_qs.order_by('store__name', 'name'):
        agg = agg_map.get(s.id, {})
        reg = agg.get('total_regular') or 0
        ot = agg.get('total_overtime') or 0
        ln = agg.get('total_late_night') or 0
        hol = agg.get('total_holiday') or 0
        brk = agg.get('total_break') or 0

        result.append({
            'staff_id': s.id,
            'staff_name': s.name,
            'store_name': s.store.name,
            'attendance_days': agg.get('attendance_days') or 0,
            'regular_minutes': reg,
            'overtime_minutes': ot,
            'late_night_minutes': ln,
            'holiday_minutes': hol,
            'break_minutes': brk,
            'total_minutes': reg + ot + ln + hol,
        })
    return result
