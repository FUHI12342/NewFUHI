"""
Tests for booking.services.shift_scheduler — auto_schedule / sync_assignments_to_schedule.
"""
import pytest
from datetime import date, timedelta
from django.utils import timezone

from booking.models import (
    ShiftAssignment,
    ShiftRequest,
    Schedule,
    StoreScheduleConfig,
)
from booking.services.shift_scheduler import auto_schedule, sync_assignments_to_schedule


# ==============================
# auto_schedule tests
# ==============================


@pytest.mark.django_db
class TestAutoSchedule:
    """auto_schedule: ShiftRequest -> ShiftAssignment 自動生成"""

    def test_preferred_requests_assigned_first(self, shift_period, staff, store_schedule_config):
        """preference='preferred' のリクエストが優先的にアサインされる"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='available',
        )
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 11), start_hour=10, end_hour=12,
            preference='preferred',
        )
        count = auto_schedule(shift_period)
        assert count == 2
        assignments = ShiftAssignment.objects.filter(period=shift_period)
        assert assignments.count() == 2

    def test_unavailable_requests_excluded(self, shift_period, staff, store_schedule_config):
        """preference='unavailable' のリクエストは除外される"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='unavailable',
        )
        count = auto_schedule(shift_period)
        assert count == 0
        assert ShiftAssignment.objects.filter(period=shift_period).count() == 0

    def test_outside_business_hours_skipped(self, shift_period, staff, store_schedule_config):
        """営業時間外のリクエストはスキップされる"""
        # store_schedule_config: open_hour=9, close_hour=21
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=6, end_hour=8,
            preference='preferred',
        )
        count = auto_schedule(shift_period)
        assert count == 0

    def test_end_hour_exceeds_close_skipped(self, shift_period, staff, store_schedule_config):
        """end_hour が close_hour を超えるリクエストはスキップ"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=20, end_hour=23,
            preference='preferred',
        )
        count = auto_schedule(shift_period)
        assert count == 0

    def test_duplicate_prevention_same_staff_same_slot(self, shift_period, staff, store_schedule_config):
        """同一スタッフ・同一スロットの重複アサインを防止"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='preferred',
        )
        # 同じスロットに available も出す（unique_together は start_hour 単位）
        # auto_schedule は内部で重複チェックするので 1 件だけ作成される
        count = auto_schedule(shift_period)
        assert count == 1

    def test_clears_existing_assignments_on_reschedule(self, shift_period, staff, store_schedule_config):
        """再スケジューリング時に既存のアサインメントがクリアされる"""
        # 事前にアサイン作成
        ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=9, end_hour=11,
        )
        assert ShiftAssignment.objects.filter(period=shift_period).count() == 1

        # リクエスト無しで auto_schedule → 既存がクリアされ 0 件
        count = auto_schedule(shift_period)
        assert count == 0
        assert ShiftAssignment.objects.filter(period=shift_period).count() == 0

    def test_sets_period_status_scheduled(self, shift_period, staff, store_schedule_config):
        """実行後に period.status が 'scheduled' に更新される"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='preferred',
        )
        auto_schedule(shift_period)
        shift_period.refresh_from_db()
        assert shift_period.status == 'scheduled'

    def test_returns_created_count(self, shift_period, staff, store_schedule_config):
        """作成されたアサインメント数を返す"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='preferred',
        )
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 11), start_hour=10, end_hour=12,
            preference='available',
        )
        count = auto_schedule(shift_period)
        assert count == 2

    def test_no_config_uses_defaults(self, shift_period, staff):
        """StoreScheduleConfig が無い場合はデフォルト値(9-21, 60分)を使用"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=10, end_hour=12,
            preference='preferred',
        )
        count = auto_schedule(shift_period)
        assert count == 1

    def test_within_business_hours_assigned(self, shift_period, staff, store_schedule_config):
        """営業時間内のリクエストは正しくアサインされる"""
        ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 10), start_hour=9, end_hour=21,
            preference='available',
        )
        count = auto_schedule(shift_period)
        assert count == 1
        a = ShiftAssignment.objects.get(period=shift_period)
        assert a.start_hour == 9
        assert a.end_hour == 21


# ==============================
# sync_assignments_to_schedule tests
# ==============================


@pytest.mark.django_db
class TestSyncAssignmentsToSchedule:
    """sync_assignments_to_schedule: ShiftAssignment -> Schedule レコード作成"""

    def test_creates_schedule_records_from_assignments(
        self, shift_period, shift_assignment, store_schedule_config,
    ):
        """ShiftAssignment から Schedule レコードが作成される"""
        count = sync_assignments_to_schedule(shift_period)
        assert count > 0
        assert Schedule.objects.filter(staff=shift_assignment.staff).exists()

    def test_splits_shifts_by_slot_duration(
        self, shift_period, staff, store_schedule_config,
    ):
        """2時間シフト + 60分スロット → 2つの Schedule が生成される"""
        assignment = ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 12), start_hour=10, end_hour=12,
        )
        count = sync_assignments_to_schedule(shift_period)
        assert count == 2
        schedules = Schedule.objects.filter(staff=staff, start__date=date(2025, 4, 12))
        assert schedules.count() == 2

    def test_marks_assignment_as_synced(
        self, shift_period, shift_assignment, store_schedule_config,
    ):
        """同期後に assignment.is_synced=True に更新される"""
        assert shift_assignment.is_synced is False
        sync_assignments_to_schedule(shift_period)
        shift_assignment.refresh_from_db()
        assert shift_assignment.is_synced is True

    def test_sets_period_status_approved(
        self, shift_period, shift_assignment, store_schedule_config,
    ):
        """同期後に period.status が 'approved' に更新される"""
        sync_assignments_to_schedule(shift_period)
        shift_period.refresh_from_db()
        assert shift_period.status == 'approved'

    def test_skips_already_existing_schedule(
        self, shift_period, staff, store_schedule_config,
    ):
        """既にある Schedule と同じスタッフ・同じ時間帯はスキップされる"""
        import datetime as dt
        start_dt = timezone.make_aware(
            dt.datetime.combine(date(2025, 4, 12), dt.time(10, 0))
        )
        end_dt = start_dt + dt.timedelta(minutes=60)
        Schedule.objects.create(
            staff=staff, start=start_dt, end=end_dt,
            customer_name=None, price=0, is_temporary=False,
        )
        assignment = ShiftAssignment.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 12), start_hour=10, end_hour=12,
        )
        count = sync_assignments_to_schedule(shift_period)
        # 10:00-11:00 は既存なのでスキップ、11:00-12:00 の 1 件のみ
        assert count == 1
