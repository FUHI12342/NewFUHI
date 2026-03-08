"""
Tests for booking/services/attendance_service.py

Covers:
- _calc_break_minutes: statutory break time calculation
- _classify_work_hours: classification into regular/overtime/late-night/holiday
- derive_attendance_from_shifts: auto-generation of WorkAttendance from ShiftAssignment
"""
import pytest
from datetime import date, time

from booking.models import WorkAttendance, ShiftAssignment
from booking.services.attendance_service import (
    _calc_break_minutes,
    _classify_work_hours,
    derive_attendance_from_shifts,
)


# ==============================
# _calc_break_minutes
# ==============================

class TestCalcBreakMinutes:

    def test_under_4_5_hours_no_break(self):
        """Under 4.5 hours (270 min) of work requires no break."""
        assert _calc_break_minutes(240) == 0
        assert _calc_break_minutes(269) == 0

    def test_exactly_270_minutes_45_break(self):
        """Exactly 4.5 hours (270 min) triggers 45-minute break."""
        assert _calc_break_minutes(270) == 45

    def test_between_4_5_and_6_hours_45_break(self):
        """Between 4.5h and 6h: 45-minute break."""
        assert _calc_break_minutes(300) == 45
        assert _calc_break_minutes(359) == 45

    def test_exactly_360_minutes_60_break(self):
        """Exactly 6 hours (360 min) triggers 60-minute break."""
        assert _calc_break_minutes(360) == 60

    def test_over_6_hours_60_break(self):
        """Over 6 hours: 60-minute break."""
        assert _calc_break_minutes(480) == 60
        assert _calc_break_minutes(600) == 60

    def test_zero_minutes_no_break(self):
        """Zero work minutes means no break."""
        assert _calc_break_minutes(0) == 0


# ==============================
# _classify_work_hours
# ==============================

class TestClassifyWorkHours:

    def test_normal_day_9_to_17(self):
        """9:00-17:00 (8h total, 60min break) -> regular=420, overtime=60, late_night=0."""
        result = _classify_work_hours(9, 17)
        assert result['break_minutes'] == 60
        # net_work = 480 - 60 = 420 daytime, 0 late-night
        # daytime=420 <= 480 => regular=420, overtime=0
        assert result['regular_minutes'] == 420
        assert result['overtime_minutes'] == 0
        assert result['late_night_minutes'] == 0
        assert result['holiday_minutes'] == 0

    def test_normal_day_9_to_18(self):
        """9:00-18:00 (9h total, 60min break) -> net=480, regular=480, overtime=0."""
        result = _classify_work_hours(9, 18)
        assert result['break_minutes'] == 60
        # net = 540 - 60 = 480, all daytime
        assert result['regular_minutes'] == 480
        assert result['overtime_minutes'] == 0

    def test_overtime_9_to_19(self):
        """9:00-19:00 (10h, 60min break) -> net=540, regular=480, overtime=60."""
        result = _classify_work_hours(9, 19)
        assert result['break_minutes'] == 60
        assert result['regular_minutes'] == 480
        assert result['overtime_minutes'] == 60
        assert result['late_night_minutes'] == 0

    def test_night_shift_crossing_22(self):
        """18:00-23:00 (5h, 45min break) -> late_night=60 (22:00 hour)."""
        result = _classify_work_hours(18, 23)
        assert result['break_minutes'] == 45
        # late_night: hours 22 counted -> 60 min
        assert result['late_night_minutes'] == 60
        # net_work = 300 - 45 = 255, daytime = 255 - 60 = 195
        assert result['regular_minutes'] == 195
        assert result['overtime_minutes'] == 0

    def test_deep_night_shift(self):
        """20:00-24:00 (4h=240min, <4.5h so 0 break) -> late_night=120 (hours 22, 23)."""
        result = _classify_work_hours(20, 24)
        # 240 min < 270 min (4.5h threshold) -> no break
        assert result['break_minutes'] == 0
        # hours 22, 23 are late-night -> 120 min
        assert result['late_night_minutes'] == 120

    def test_short_shift_no_break(self):
        """9:00-13:00 (4h, 0 break) -> regular=240, no break."""
        result = _classify_work_hours(9, 13)
        assert result['break_minutes'] == 0
        assert result['regular_minutes'] == 240
        assert result['overtime_minutes'] == 0

    def test_holiday_all_goes_to_holiday_minutes(self):
        """Holiday: all non-late-night minutes go to holiday_minutes."""
        result = _classify_work_hours(9, 17, is_holiday=True)
        assert result['regular_minutes'] == 0
        assert result['overtime_minutes'] == 0
        assert result['late_night_minutes'] == 0
        assert result['holiday_minutes'] == 420  # 480 - 60 break
        assert result['break_minutes'] == 60

    def test_holiday_with_late_night(self):
        """Holiday shift crossing 22:00 has both holiday and late_night."""
        result = _classify_work_hours(18, 23, is_holiday=True)
        # late_night: hour 22 -> 60 min
        assert result['late_night_minutes'] == 60
        # holiday = net_work - late_night = (300-45) - 60 = 195
        assert result['holiday_minutes'] == 195
        assert result['regular_minutes'] == 0
        assert result['overtime_minutes'] == 0

    def test_early_morning_hours_before_5(self):
        """Hours before 5:00 (0-4) count as late-night."""
        result = _classify_work_hours(0, 8)
        # hours 0,1,2,3,4 are late-night (< 5) -> 300 min
        assert result['late_night_minutes'] == 300
        assert result['break_minutes'] == 60


# ==============================
# derive_attendance_from_shifts
# ==============================

class TestDeriveAttendanceFromShifts:

    @pytest.mark.django_db
    def test_creates_work_attendance_from_shift(self, store, shift_period, shift_assignment):
        """Creates WorkAttendance record from ShiftAssignment."""
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 1
        att = WorkAttendance.objects.get(staff=shift_assignment.staff, date=shift_assignment.date)
        assert att.source == 'shift'
        assert att.source_assignment == shift_assignment

    @pytest.mark.django_db
    def test_skips_manual_records(self, store, staff, shift_period, shift_assignment):
        """Existing manual attendance records should not be overwritten."""
        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 10),
            clock_in=time(10, 0), clock_out=time(18, 0),
            regular_minutes=420, overtime_minutes=60,
            late_night_minutes=0, holiday_minutes=0, break_minutes=60,
            source='manual',
        )
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 0

    @pytest.mark.django_db
    def test_skips_corrected_records(self, store, staff, shift_period, shift_assignment):
        """Existing corrected attendance records should not be overwritten."""
        WorkAttendance.objects.create(
            staff=staff, date=date(2025, 4, 10),
            clock_in=time(10, 0), clock_out=time(18, 0),
            regular_minutes=420, overtime_minutes=60,
            late_night_minutes=0, holiday_minutes=0, break_minutes=60,
            source='corrected',
        )
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 0

    @pytest.mark.django_db
    def test_sunday_detected_as_holiday(self, store, staff, shift_period):
        """Sunday (weekday==6) should be flagged as holiday."""
        # 2025-04-13 is a Sunday
        sunday = date(2025, 4, 13)
        assert sunday.weekday() == 6
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=sunday, start_hour=9, end_hour=17,
        )
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 1
        att = WorkAttendance.objects.get(staff=staff, date=sunday)
        # Holiday: regular=0, holiday_minutes > 0
        assert att.regular_minutes == 0
        assert att.holiday_minutes > 0

    @pytest.mark.django_db
    def test_updates_existing_shift_record(self, store, staff, shift_period, shift_assignment):
        """If a 'shift' source record exists, update_or_create should update it."""
        # First derivation
        derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        # Change the shift assignment hours
        shift_assignment.end_hour = 19
        shift_assignment.save()
        # Second derivation should update, not create a duplicate
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 1
        assert WorkAttendance.objects.filter(staff=staff, date=date(2025, 4, 10)).count() == 1

    @pytest.mark.django_db
    def test_no_assignments_returns_zero(self, store):
        """No shift assignments means 0 records created."""
        count = derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        assert count == 0

    @pytest.mark.django_db
    def test_clock_in_and_clock_out_set(self, store, shift_period, shift_assignment):
        """Clock-in and clock-out times should be derived from assignment hours."""
        derive_attendance_from_shifts(store, date(2025, 4, 1), date(2025, 4, 30))
        att = WorkAttendance.objects.get(staff=shift_assignment.staff, date=shift_assignment.date)
        assert att.clock_in == time(9, 0)
        assert att.clock_out == time(17, 0)
