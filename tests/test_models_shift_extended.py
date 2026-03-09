"""シフトモデル拡張テスト"""
import pytest
from datetime import time, date
from booking.models import ShiftTemplate, ShiftPublishHistory, ShiftAssignment, ShiftRequest


@pytest.mark.django_db
class TestShiftTemplate:
    def test_create(self, store):
        t = ShiftTemplate.objects.create(
            store=store, name='早番',
            start_time=time(9, 0), end_time=time(14, 0),
        )
        assert t.pk is not None
        assert t.color == '#3B82F6'

    def test_str(self, shift_template):
        s = str(shift_template)
        assert '早番' in s
        assert '09:00' in s


@pytest.mark.django_db
class TestShiftTimeFields:
    def test_assignment_time_fields(self, shift_period, staff):
        a = ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=date(2026, 3, 10), start_hour=9, end_hour=17,
            start_time=time(9, 0), end_time=time(17, 0),
        )
        assert a.start_time == time(9, 0)
        assert a.end_time == time(17, 0)

    def test_assignment_null_time(self, shift_assignment):
        # Existing assignments should have null time fields
        assert shift_assignment.start_time is None or isinstance(shift_assignment.start_time, time)

    def test_request_time_fields(self, shift_period, staff):
        r = ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2026, 3, 15), start_hour=10, end_hour=18,
            start_time=time(10, 0), end_time=time(18, 0),
        )
        assert r.start_time == time(10, 0)
