"""
Tests for shift-related models:
StoreScheduleConfig, ShiftPeriod, ShiftRequest, ShiftAssignment.
"""
import pytest
from datetime import date

from django.db import IntegrityError

from booking.models import (
    StoreScheduleConfig,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
)


# ==============================
# StoreScheduleConfig
# ==============================


@pytest.mark.django_db
class TestStoreScheduleConfig:
    """StoreScheduleConfig モデルテスト"""

    def test_defaults(self, store_schedule_config):
        """デフォルト値: open_hour=9, close_hour=21, slot_duration=60"""
        assert store_schedule_config.open_hour == 9
        assert store_schedule_config.close_hour == 21
        assert store_schedule_config.slot_duration == 60

    def test_str_format(self, store_schedule_config):
        """__str__ が '店舗名 (開始:00-終了:00 / コマ分)' 形式"""
        s = str(store_schedule_config)
        assert store_schedule_config.store.name in s
        assert '9:00' in s
        assert '21:00' in s
        assert '60分' in s

    def test_one_to_one_with_store(self, store_schedule_config, store):
        """Store との 1:1 関係 (重複作成でエラー)"""
        with pytest.raises(IntegrityError):
            StoreScheduleConfig.objects.create(
                store=store, open_hour=10, close_hour=20, slot_duration=30,
            )


# ==============================
# ShiftPeriod
# ==============================


@pytest.mark.django_db
class TestShiftPeriod:
    """ShiftPeriod モデルテスト"""

    def test_status_choices(self, shift_period):
        """status が有効な選択肢の一つ"""
        valid = ['open', 'closed', 'scheduled', 'approved']
        assert shift_period.status in valid

    def test_str_format(self, shift_period):
        """__str__ が '店舗名 YYYY年MM月 (ステータス表示)' 形式"""
        s = str(shift_period)
        assert shift_period.store.name in s
        assert '2025年04月' in s
        assert '募集中' in s  # status='open' → '募集中'

    def test_default_status_is_open(self, shift_period):
        """デフォルトの status が 'open'"""
        assert shift_period.status == 'open'


# ==============================
# ShiftRequest
# ==============================


@pytest.mark.django_db
class TestShiftRequest:
    """ShiftRequest モデルテスト"""

    def test_preference_choices(self, shift_request):
        """preference が有効な選択肢の一つ"""
        valid = ['available', 'preferred', 'unavailable']
        assert shift_request.preference in valid

    def test_unique_together_period_staff_date_start_hour(self, shift_request, shift_period, staff):
        """同一 (period, staff, date, start_hour) の重複でエラー"""
        with pytest.raises(IntegrityError):
            ShiftRequest.objects.create(
                period=shift_period,
                staff=staff,
                date=shift_request.date,
                start_hour=shift_request.start_hour,
                end_hour=shift_request.end_hour,
                preference='available',
            )

    def test_str_format(self, shift_request):
        """__str__ が 'スタッフ名 日付 開始:00-終了:00 (希望区分)' 形式"""
        s = str(shift_request)
        assert shift_request.staff.name in s
        assert '9:00' in s
        assert '17:00' in s
        assert '希望' in s  # preference='preferred' → '希望'

    def test_default_preference_is_available(self, shift_period, staff):
        """preference のデフォルトが 'available'"""
        req = ShiftRequest.objects.create(
            period=shift_period, staff=staff,
            date=date(2025, 4, 15), start_hour=10, end_hour=12,
        )
        assert req.preference == 'available'


# ==============================
# ShiftAssignment
# ==============================


@pytest.mark.django_db
class TestShiftAssignment:
    """ShiftAssignment モデルテスト"""

    def test_is_synced_default_false(self, shift_assignment):
        """is_synced のデフォルトが False"""
        assert shift_assignment.is_synced is False

    def test_unique_together_period_staff_date_start_hour(
        self, shift_assignment, shift_period, staff,
    ):
        """同一 (period, staff, date, start_hour) の重複でエラー"""
        with pytest.raises(IntegrityError):
            ShiftAssignment.objects.create(
                period=shift_period,
                staff=staff,
                date=shift_assignment.date,
                start_hour=shift_assignment.start_hour,
                end_hour=shift_assignment.end_hour,
            )

    def test_str_format(self, shift_assignment):
        """__str__ が 'スタッフ名 日付 開始:00-終了:00' 形式"""
        s = str(shift_assignment)
        assert shift_assignment.staff.name in s
        assert '9:00' in s
        assert '17:00' in s

    def test_can_set_synced_true(self, shift_assignment):
        """is_synced を True に更新できる"""
        shift_assignment.is_synced = True
        shift_assignment.save(update_fields=['is_synced'])
        shift_assignment.refresh_from_db()
        assert shift_assignment.is_synced is True
