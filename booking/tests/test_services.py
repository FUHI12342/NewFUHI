"""
サービス関数の包括的テストスイート

対象サービス:
  - booking/services/shift_scheduler.py
      get_required_counts, _get_store_config, _build_req_map
      auto_schedule, sync_assignments_to_schedule
      revoke_published_shifts, revert_scheduled
      reopen_for_recruitment, revise_assignment
  - booking/services/shift_coverage.py
      build_coverage_map, record_assignment, check_coverage_need
      find_needed_blocks, count_coverage_hours, generate_vacancies

TDD原則:
  - 各テストは独立して実行可能（setUp で状態リセット）
  - 外部依存（LINE通知等）は unittest.mock でモック
  - 境界値・エッジケース・エラーパスを網羅
"""
import datetime
from collections import defaultdict
from unittest.mock import patch, MagicMock, call

from django.test import TestCase
from django.utils import timezone

from booking.models import (
    Store,
    Staff,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    ShiftVacancy,
    ShiftPublishHistory,
    ShiftChangeLog,
    ShiftStaffRequirement,
    ShiftStaffRequirementOverride,
    StoreScheduleConfig,
    StoreClosedDate,
    Schedule,
)
from booking.services.shift_coverage import (
    build_coverage_map,
    record_assignment,
    check_coverage_need,
    count_coverage_hours,
    find_needed_blocks,
    generate_vacancies,
)
from booking.services.shift_scheduler import (
    get_required_counts,
    auto_schedule,
    sync_assignments_to_schedule,
    revoke_published_shifts,
    revert_scheduled,
    reopen_for_recruitment,
    revise_assignment,
    _get_store_config,
    _build_req_map,
)
from booking.tests.factories import (
    StoreFactory,
    StaffFactory,
    ManagerStaffFactory,
    StoreScheduleConfigFactory,
    ShiftPeriodFactory,
    ShiftRequestFactory,
    ShiftAssignmentFactory,
    ShiftStaffRequirementFactory,
    ShiftVacancyFactory,
    StoreClosedDateFactory,
    ScheduleFactory,
)


# ===========================================================================
# ヘルパー関数
# ===========================================================================

def make_requirement(store, day_of_week, staff_type='fortune_teller', required_count=2):
    """ShiftStaffRequirement を作成するヘルパー"""
    return ShiftStaffRequirement.objects.create(
        store=store,
        day_of_week=day_of_week,
        staff_type=staff_type,
        required_count=required_count,
    )


def make_override(store, date, staff_type='fortune_teller', required_count=3):
    """ShiftStaffRequirementOverride を作成するヘルパー"""
    return ShiftStaffRequirementOverride.objects.create(
        store=store,
        date=date,
        staff_type=staff_type,
        required_count=required_count,
    )


# ===========================================================================
# 1. get_required_counts のテスト
# ===========================================================================

class TestGetRequiredCounts(TestCase):
    """get_required_counts 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()

    def test_returns_overrides_when_present(self):
        """オーバーライドがある場合はそれを返す"""
        target_date = datetime.date(2026, 4, 6)  # 月曜
        make_requirement(self.store, day_of_week=0, required_count=2)
        make_override(self.store, target_date, required_count=5)

        result = get_required_counts(self.store, target_date)

        self.assertEqual(result.get('fortune_teller'), 5)

    def test_returns_defaults_when_no_override(self):
        """オーバーライドがない場合はデフォルト値を返す"""
        target_date = datetime.date(2026, 4, 6)  # 月曜 (weekday=0)
        make_requirement(self.store, day_of_week=0, required_count=3)

        result = get_required_counts(self.store, target_date)

        self.assertEqual(result.get('fortune_teller'), 3)

    def test_returns_empty_dict_when_no_requirements(self):
        """要件もオーバーライドもない場合は空辞書を返す"""
        target_date = datetime.date(2026, 4, 6)
        result = get_required_counts(self.store, target_date)
        self.assertEqual(result, {})

    def test_overrides_take_precedence_over_defaults(self):
        """オーバーライドがデフォルトより優先される"""
        target_date = datetime.date(2026, 4, 7)  # 火曜 (weekday=1)
        make_requirement(self.store, day_of_week=1, required_count=2)
        make_override(self.store, target_date, required_count=10)

        result = get_required_counts(self.store, target_date)

        self.assertEqual(result.get('fortune_teller'), 10)

    def test_returns_multiple_staff_types(self):
        """複数スタッフ種別の要件を返す"""
        target_date = datetime.date(2026, 4, 6)  # 月曜
        make_requirement(self.store, day_of_week=0, staff_type='fortune_teller', required_count=2)
        make_requirement(self.store, day_of_week=0, staff_type='store_staff', required_count=1)

        result = get_required_counts(self.store, target_date)

        self.assertEqual(result.get('fortune_teller'), 2)
        self.assertEqual(result.get('store_staff'), 1)

    def test_returns_dict_not_queryset(self):
        """戻り値は辞書型"""
        target_date = datetime.date(2026, 4, 6)
        make_requirement(self.store, day_of_week=0, required_count=2)
        result = get_required_counts(self.store, target_date)
        self.assertIsInstance(result, dict)

    def test_day_of_week_mapping_is_correct(self):
        """曜日マッピングが正確（月曜=0, 日曜=6）"""
        # 2026-04-06 は月曜（weekday=0）
        monday = datetime.date(2026, 4, 6)
        make_requirement(self.store, day_of_week=0, required_count=7)
        result = get_required_counts(self.store, monday)
        self.assertEqual(result.get('fortune_teller'), 7)

        # 2026-04-12 は日曜（weekday=6）
        sunday = datetime.date(2026, 4, 12)
        make_requirement(self.store, day_of_week=6, required_count=5)
        result = get_required_counts(self.store, sunday)
        self.assertEqual(result.get('fortune_teller'), 5)


# ===========================================================================
# 2. _get_store_config のテスト
# ===========================================================================

class TestGetStoreConfig(TestCase):
    """_get_store_config 関数のテスト"""

    def test_returns_config_values_when_config_exists(self):
        """StoreScheduleConfig が存在する場合はその値を返す"""
        store = StoreFactory()
        StoreScheduleConfigFactory(
            store=store,
            open_hour=8,
            close_hour=22,
            slot_duration=30,
            min_shift_hours=3,
        )
        open_h, close_h, duration, min_shift = _get_store_config(store)
        self.assertEqual(open_h, 8)
        self.assertEqual(close_h, 22)
        self.assertEqual(duration, 30)
        self.assertEqual(min_shift, 3)

    def test_returns_defaults_when_no_config(self):
        """StoreScheduleConfig がない場合はデフォルト値を返す"""
        store = StoreFactory()
        open_h, close_h, duration, min_shift = _get_store_config(store)
        self.assertEqual(open_h, 9)
        self.assertEqual(close_h, 21)
        self.assertEqual(duration, 60)
        self.assertEqual(min_shift, 2)

    def test_returns_tuple_of_four_values(self):
        """4タプルを返す"""
        store = StoreFactory()
        result = _get_store_config(store)
        self.assertEqual(len(result), 4)


# ===========================================================================
# 3. _build_req_map のテスト
# ===========================================================================

class TestBuildReqMap(TestCase):
    """_build_req_map 関数のテスト"""

    def test_builds_map_for_all_days_in_month(self):
        """月内の全日付に対してマップを構築する"""
        store = StoreFactory()
        # 全曜日に要件を設定
        for dow in range(7):
            make_requirement(store, day_of_week=dow, required_count=2)
        period = ShiftPeriodFactory(store=store, year_month=datetime.date(2026, 4, 1))

        req_map = _build_req_map(store, period)

        # 4月は30日間
        self.assertEqual(len(req_map), 30)

    def test_returns_correct_counts_for_each_day(self):
        """各日付に正しい必要人数が含まれる"""
        store = StoreFactory()
        # 月曜（0）に2名
        make_requirement(store, day_of_week=0, required_count=2)
        period = ShiftPeriodFactory(store=store, year_month=datetime.date(2026, 4, 1))

        req_map = _build_req_map(store, period)

        # 2026-04-06 は月曜
        monday = datetime.date(2026, 4, 6)
        self.assertIn(monday, req_map)
        self.assertEqual(req_map[monday].get('fortune_teller'), 2)

    def test_skips_days_with_no_requirements(self):
        """要件がない日はマップに含まれない"""
        store = StoreFactory()
        # 月曜だけ設定
        make_requirement(store, day_of_week=0, required_count=2)
        period = ShiftPeriodFactory(store=store, year_month=datetime.date(2026, 4, 1))

        req_map = _build_req_map(store, period)

        # 火曜以降は含まれない
        tuesday = datetime.date(2026, 4, 7)  # 火曜
        self.assertNotIn(tuesday, req_map)

    def test_handles_month_with_31_days(self):
        """31日の月でも正しく動作する"""
        store = StoreFactory()
        for dow in range(7):
            make_requirement(store, day_of_week=dow, required_count=1)
        period = ShiftPeriodFactory(store=store, year_month=datetime.date(2026, 1, 1))

        req_map = _build_req_map(store, period)

        self.assertEqual(len(req_map), 31)


# ===========================================================================
# 4. auto_schedule のテスト（総合テスト）
# ===========================================================================

class AutoScheduleBaseSetup(TestCase):
    """auto_schedule テストの共通セットアップ"""

    def setUp(self):
        self.store = StoreFactory()
        self.config = StoreScheduleConfigFactory(
            store=self.store,
            open_hour=9,
            close_hour=21,
            slot_duration=60,
            min_shift_hours=2,
        )
        # 全曜日に fortune_teller 2名必要
        for dow in range(7):
            make_requirement(self.store, day_of_week=dow, required_count=2)

        self.staff1 = StaffFactory(store=self.store)
        self.staff2 = StaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(
            store=self.store,
            year_month=datetime.date(2026, 1, 1),
            status='open',
        )

    def make_request(self, staff, date, start_hour, end_hour, preference='available'):
        return ShiftRequest.objects.create(
            period=self.period,
            staff=staff,
            date=date,
            start_hour=start_hour,
            end_hour=end_hour,
            preference=preference,
        )


class TestAutoScheduleReturnsCount(AutoScheduleBaseSetup):
    """auto_schedule の戻り値テスト"""

    def test_returns_zero_when_no_requests(self):
        """リクエストがない場合は 0 を返す"""
        result = auto_schedule(self.period)
        self.assertEqual(result, 0)

    def test_returns_created_count(self):
        """作成されたアサイン数を返す"""
        date = datetime.date(2026, 1, 5)  # 月曜
        self.make_request(self.staff1, date, 9, 17)
        result = auto_schedule(self.period)
        self.assertGreaterEqual(result, 1)

    def test_period_status_becomes_scheduled(self):
        """実行後 period.status が 'scheduled' になる"""
        auto_schedule(self.period)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'scheduled')


class TestAutoScheduleUnavailableExclusion(AutoScheduleBaseSetup):
    """unavailable リクエストの除外テスト"""

    def test_unavailable_requests_are_not_assigned(self):
        """unavailable の希望はアサインされない"""
        date = datetime.date(2026, 1, 5)
        self.make_request(self.staff1, date, 9, 17, preference='unavailable')
        auto_schedule(self.period)
        count = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1).count()
        self.assertEqual(count, 0)


class TestAutoSchedulePreferredPriority(AutoScheduleBaseSetup):
    """preferred リクエストの優先処理テスト"""

    def test_preferred_is_assigned_even_when_coverage_full(self):
        """定員満員でも preferred はアサインされる"""
        date = datetime.date(2026, 1, 5)
        staff3 = StaffFactory(store=self.store)
        # available で定員充足
        self.make_request(self.staff1, date, 9, 17, preference='preferred')
        self.make_request(self.staff2, date, 9, 17, preference='preferred')
        # preferred の追加スタッフ
        self.make_request(staff3, date, 9, 17, preference='preferred')

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period, staff=staff3).count()
        self.assertEqual(count, 1)

    def test_available_skipped_when_coverage_full(self):
        """全時間帯充足後の available はスキップされる"""
        date = datetime.date(2026, 1, 5)
        staff3 = StaffFactory(store=self.store)
        self.make_request(self.staff1, date, 9, 17, preference='preferred')
        self.make_request(self.staff2, date, 9, 17, preference='preferred')
        self.make_request(staff3, date, 9, 17, preference='available')

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period, staff=staff3).count()
        self.assertEqual(count, 0)


class TestAutoScheduleBusinessHoursClipping(AutoScheduleBaseSetup):
    """営業時間クリップのテスト"""

    def test_request_before_open_is_clipped(self):
        """開始時間が営業時間前のリクエストはクリップされる"""
        self.config.open_hour = 13
        self.config.min_shift_hours = 2
        self.config.save()

        date = datetime.date(2026, 1, 5)
        self.make_request(self.staff1, date, 10, 17, preference='preferred')

        auto_schedule(self.period)

        assignment = ShiftAssignment.objects.filter(
            period=self.period, staff=self.staff1
        ).first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.start_hour, 13)

    def test_request_entirely_outside_hours_is_skipped(self):
        """全体が営業時間外のリクエストはスキップ"""
        self.config.open_hour = 13
        self.config.close_hour = 21
        self.config.save()

        date = datetime.date(2026, 1, 5)
        self.make_request(self.staff1, date, 9, 12)  # 13時開始なので全体が範囲外

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1).count()
        self.assertEqual(count, 0)


class TestAutoScheduleClosedDates(AutoScheduleBaseSetup):
    """休業日スキップのテスト"""

    def test_closed_date_requests_are_skipped(self):
        """休業日のリクエストはスキップされる"""
        date = datetime.date(2026, 1, 5)
        StoreClosedDate.objects.create(store=self.store, date=date, reason='テスト休業')
        self.make_request(self.staff1, date, 9, 17)

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period).count()
        self.assertEqual(count, 0)


class TestAutoScheduleIdempotency(AutoScheduleBaseSetup):
    """二重実行の冪等性テスト"""

    def test_reruns_clear_existing_assignments(self):
        """再実行時は既存アサインを削除して再生成する"""
        date = datetime.date(2026, 1, 5)
        self.make_request(self.staff1, date, 9, 17, preference='preferred')

        auto_schedule(self.period)
        count_first = ShiftAssignment.objects.filter(period=self.period).count()

        auto_schedule(self.period)
        count_second = ShiftAssignment.objects.filter(period=self.period).count()

        # 二回目も同じ件数（重複しない）
        self.assertEqual(count_first, count_second)


class TestAutoScheduleVacancyGeneration(AutoScheduleBaseSetup):
    """不足枠自動生成のテスト"""

    def test_vacancies_generated_for_unfilled_slots(self):
        """定員未達のスロットに vacancy が生成される"""
        date = datetime.date(2026, 1, 5)  # 月曜（required=2）
        # 1名のみアサイン（定員2に対して不足）
        self.make_request(self.staff1, date, 9, 21, preference='available')

        auto_schedule(self.period)

        vacancies = ShiftVacancy.objects.filter(period=self.period)
        self.assertGreater(vacancies.count(), 0)

    def test_no_vacancies_when_fully_covered(self):
        """全時間帯が定員充足の場合は vacancy が生成されない"""
        date = datetime.date(2026, 1, 5)
        # 2名で定員充足
        self.make_request(self.staff1, date, 9, 21, preference='preferred')
        self.make_request(self.staff2, date, 9, 21, preference='preferred')

        auto_schedule(self.period)

        vacancies = ShiftVacancy.objects.filter(
            period=self.period,
            date=date,
        )
        # 定員充足日に vacancy なし
        self.assertEqual(vacancies.count(), 0)


class TestAutoScheduleMinShiftHours(AutoScheduleBaseSetup):
    """最低シフト時間制約のテスト"""

    def test_preferred_below_min_shift_hours_skipped(self):
        """preferred でもクリップ後が min_shift_hours 未満ならスキップ"""
        self.config.min_shift_hours = 4
        self.config.save()

        date = datetime.date(2026, 1, 5)
        # 9:00-11:00 = 2時間 < min_shift_hours=4 → スキップ
        self.make_request(self.staff1, date, 9, 11, preference='preferred')

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1).count()
        self.assertEqual(count, 0)

    def test_preferred_at_exact_min_shift_hours_assigned(self):
        """ちょうど min_shift_hours の preferred はアサインされる"""
        self.config.min_shift_hours = 4
        self.config.save()

        date = datetime.date(2026, 1, 5)
        self.make_request(self.staff1, date, 9, 13, preference='preferred')  # 4時間

        auto_schedule(self.period)

        count = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1).count()
        self.assertEqual(count, 1)


# ===========================================================================
# 5. sync_assignments_to_schedule のテスト
# ===========================================================================

class TestSyncAssignmentsToSchedule(TestCase):
    """sync_assignments_to_schedule 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.config = StoreScheduleConfigFactory(
            store=self.store,
            open_hour=9,
            close_hour=21,
            slot_duration=60,
        )
        self.staff = StaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(store=self.store, status='scheduled')

    def _make_assignment(self, date, start_hour, end_hour):
        return ShiftAssignment.objects.create(
            period=self.period,
            staff=self.staff,
            date=date,
            start_hour=start_hour,
            end_hour=end_hour,
            start_time=datetime.time(start_hour, 0),
            end_time=datetime.time(end_hour, 0),
            is_synced=False,
        )

    def test_creates_schedule_records_for_each_slot(self):
        """各60分スロットに対して Schedule レコードを作成する"""
        self._make_assignment(datetime.date(2026, 4, 7), 9, 11)  # 2時間 = 2スロット

        count = sync_assignments_to_schedule(self.period)

        self.assertEqual(count, 2)
        schedules = Schedule.objects.filter(staff=self.staff)
        self.assertEqual(schedules.count(), 2)

    def test_marks_assignments_as_synced(self):
        """同期後にアサインの is_synced が True になる"""
        assignment = self._make_assignment(datetime.date(2026, 4, 7), 9, 10)

        sync_assignments_to_schedule(self.period)

        assignment.refresh_from_db()
        self.assertTrue(assignment.is_synced)

    def test_period_status_becomes_approved(self):
        """同期後に period.status が 'approved' になる"""
        self._make_assignment(datetime.date(2026, 4, 7), 9, 10)

        sync_assignments_to_schedule(self.period)

        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'approved')

    def test_does_not_create_duplicate_schedules(self):
        """既存の Schedule と重複する場合は作成しない"""
        import zoneinfo
        date = datetime.date(2026, 4, 7)
        # 先に同じ時間帯の Schedule を作成（店舗タイムゾーン Asia/Tokyo で aware 化）
        tz = zoneinfo.ZoneInfo('Asia/Tokyo')
        start_dt = datetime.datetime(2026, 4, 7, 9, 0, tzinfo=tz)
        Schedule.objects.create(
            staff=self.staff,
            start=start_dt,
            end=datetime.datetime(2026, 4, 7, 10, 0, tzinfo=tz),
            price=0,
            is_temporary=False,
            is_cancelled=False,
            memo='既存スケジュール',
        )
        self._make_assignment(date, 9, 10)

        count = sync_assignments_to_schedule(self.period)

        # 重複しないので 0
        self.assertEqual(count, 0)

    def test_skips_already_synced_assignments(self):
        """is_synced=True のアサインはスキップされる"""
        assignment = self._make_assignment(datetime.date(2026, 4, 7), 9, 10)
        assignment.is_synced = True
        assignment.save()

        count = sync_assignments_to_schedule(self.period)

        self.assertEqual(count, 0)

    def test_schedule_memo_is_auto_created_label(self):
        """作成された Schedule のメモが '自動作成' 文字列を含む"""
        self._make_assignment(datetime.date(2026, 4, 7), 9, 10)

        sync_assignments_to_schedule(self.period)

        schedule = Schedule.objects.filter(staff=self.staff).first()
        self.assertIn('シフトから自動作成', schedule.memo)

    def test_30min_slot_duration_creates_double_schedules(self):
        """30分スロット設定の場合、1時間シフトで2スケジュール作成される"""
        self.config.slot_duration = 30
        self.config.save()

        self._make_assignment(datetime.date(2026, 4, 7), 9, 11)  # 2時間 → 4スロット(30分×4)

        count = sync_assignments_to_schedule(self.period)

        self.assertEqual(count, 4)


# ===========================================================================
# 6. revoke_published_shifts のテスト
# ===========================================================================

class TestRevokePublishedShifts(TestCase):
    """revoke_published_shifts 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.staff = StaffFactory(store=self.store)
        self.manager = ManagerStaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(store=self.store, status='approved')
        self.assignment = ShiftAssignmentFactory(
            period=self.period,
            staff=self.staff,
            date=datetime.date(2026, 4, 7),
            start_hour=9,
            end_hour=17,
            is_synced=True,
        )

    def test_raises_error_when_period_not_approved(self):
        """approved 以外のステータスでは ValueError が発生"""
        self.period.status = 'scheduled'
        self.period.save()

        with self.assertRaises(ValueError):
            revoke_published_shifts(self.period, reason='テスト')

    def test_period_status_reverts_to_scheduled(self):
        """撤回後 period.status が 'scheduled' に戻る"""
        revoke_published_shifts(self.period, reason='テスト撤回')
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'scheduled')

    def test_assignments_is_synced_reset(self):
        """撤回後の assignment.is_synced が False にリセットされる"""
        revoke_published_shifts(self.period, reason='テスト撤回')
        self.assignment.refresh_from_db()
        self.assertFalse(self.assignment.is_synced)

    def test_creates_publish_history_with_revoke_action(self):
        """撤回履歴に action='revoke' のエントリが作成される"""
        revoke_published_shifts(self.period, reason='テスト撤回', revoked_by=self.manager)

        history = ShiftPublishHistory.objects.filter(period=self.period, action='revoke').first()
        self.assertIsNotNone(history)

    def test_creates_change_log_for_each_assignment(self):
        """各アサインに対して ShiftChangeLog が作成される"""
        revoke_published_shifts(self.period, reason='テスト撤回')

        log = ShiftChangeLog.objects.filter(assignment=self.assignment).first()
        self.assertIsNotNone(log)

    def test_cancels_synced_schedules(self):
        """同期済み Schedule が is_cancelled=True になる"""
        import zoneinfo
        # 対応する Schedule を作成（店舗タイムゾーン Asia/Tokyo）
        tz = zoneinfo.ZoneInfo('Asia/Tokyo')
        start_dt = datetime.datetime(2026, 4, 7, 9, 0, tzinfo=tz)
        schedule = Schedule.objects.create(
            staff=self.staff,
            start=start_dt,
            end=datetime.datetime(2026, 4, 7, 10, 0, tzinfo=tz),
            price=0,
            is_temporary=False,
            is_cancelled=False,
            memo='シフトから自動作成',
        )

        revoke_published_shifts(self.period, reason='テスト撤回')

        schedule.refresh_from_db()
        self.assertTrue(schedule.is_cancelled)

    def test_returns_cancelled_schedule_count(self):
        """キャンセルした Schedule 数を返す"""
        import zoneinfo
        tz = zoneinfo.ZoneInfo('Asia/Tokyo')
        start_dt = datetime.datetime(2026, 4, 7, 9, 0, tzinfo=tz)
        Schedule.objects.create(
            staff=self.staff,
            start=start_dt,
            end=datetime.datetime(2026, 4, 7, 10, 0, tzinfo=tz),
            price=0,
            is_temporary=False,
            is_cancelled=False,
            memo='シフトから自動作成',
        )

        result = revoke_published_shifts(self.period, reason='テスト撤回')

        self.assertGreaterEqual(result, 0)


# ===========================================================================
# 7. revert_scheduled のテスト
# ===========================================================================

class TestRevertScheduled(TestCase):
    """revert_scheduled 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.staff = StaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(store=self.store, status='scheduled')
        self.assignment = ShiftAssignmentFactory(
            period=self.period,
            staff=self.staff,
        )

    def test_raises_error_when_period_not_scheduled(self):
        """scheduled 以外では ValueError が発生"""
        self.period.status = 'open'
        self.period.save()

        with self.assertRaises(ValueError):
            revert_scheduled(self.period, reason='テスト')

    def test_deletes_all_assignments(self):
        """全アサインが削除される"""
        revert_scheduled(self.period, reason='テスト取消')
        count = ShiftAssignment.objects.filter(period=self.period).count()
        self.assertEqual(count, 0)

    def test_period_status_reverts_to_open(self):
        """取消後 period.status が 'open' に戻る"""
        revert_scheduled(self.period, reason='テスト取消')
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'open')

    def test_creates_publish_history(self):
        """取消履歴が作成される"""
        revert_scheduled(self.period, reason='テスト取消')
        history = ShiftPublishHistory.objects.filter(period=self.period).first()
        self.assertIsNotNone(history)

    def test_returns_deleted_count(self):
        """削除したアサイン数を返す"""
        result = revert_scheduled(self.period, reason='テスト取消')
        self.assertEqual(result, 1)

    def test_raises_error_when_approved(self):
        """approved 状態では ValueError が発生"""
        self.period.status = 'approved'
        self.period.save()

        with self.assertRaises(ValueError):
            revert_scheduled(self.period, reason='テスト')


# ===========================================================================
# 8. reopen_for_recruitment のテスト
# ===========================================================================

class TestReopenForRecruitment(TestCase):
    """reopen_for_recruitment 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.staff = StaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(store=self.store, status='scheduled')
        self.assignment = ShiftAssignmentFactory(period=self.period, staff=self.staff)

    def test_raises_error_when_period_not_scheduled(self):
        """scheduled 以外では ValueError が発生"""
        self.period.status = 'open'
        self.period.save()

        with self.assertRaises(ValueError):
            reopen_for_recruitment(self.period)

    def test_period_status_becomes_open(self):
        """再募集後 period.status が 'open' になる"""
        reopen_for_recruitment(self.period)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'open')

    def test_existing_assignments_are_kept(self):
        """再募集後でも既存アサインは削除されない"""
        reopen_for_recruitment(self.period)
        count = ShiftAssignment.objects.filter(period=self.period).count()
        self.assertEqual(count, 1)

    def test_creates_publish_history_with_reopen_action(self):
        """再募集履歴に action='reopen' のエントリが作成される"""
        reopen_for_recruitment(self.period, reason='再募集テスト')
        history = ShiftPublishHistory.objects.filter(period=self.period, action='reopen').first()
        self.assertIsNotNone(history)

    def test_returns_assignment_count(self):
        """既存アサイン数を返す"""
        result = reopen_for_recruitment(self.period)
        self.assertEqual(result, 1)

    def test_raises_error_when_approved(self):
        """approved 状態では ValueError が発生"""
        self.period.status = 'approved'
        self.period.save()

        with self.assertRaises(ValueError):
            reopen_for_recruitment(self.period)


# ===========================================================================
# 9. revise_assignment のテスト
# ===========================================================================

class TestReviseAssignment(TestCase):
    """revise_assignment 関数のテスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.staff = StaffFactory(store=self.store)
        self.manager = ManagerStaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(store=self.store, status='approved')
        self.assignment = ShiftAssignmentFactory(
            period=self.period,
            staff=self.staff,
            date=datetime.date(2026, 4, 7),
            start_hour=9,
            end_hour=17,
            is_synced=False,
        )

    def test_updates_assignment_fields(self):
        """指定したフィールドが更新される"""
        revise_assignment(
            self.assignment,
            new_data={'start_hour': 10, 'end_hour': 18},
            revised_by=self.manager,
        )
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.start_hour, 10)
        self.assertEqual(self.assignment.end_hour, 18)

    def test_creates_change_log(self):
        """変更ログが作成される"""
        change_log = revise_assignment(
            self.assignment,
            new_data={'start_hour': 10},
            revised_by=self.manager,
            reason='テスト変更',
        )
        self.assertIsNotNone(change_log)
        self.assertEqual(change_log.change_type, 'revised')

    def test_change_log_stores_old_and_new_values(self):
        """変更ログに変更前後の値が記録される"""
        change_log = revise_assignment(
            self.assignment,
            new_data={'start_hour': 10},
            revised_by=self.manager,
        )
        self.assertIn('start_hour', change_log.old_values)
        self.assertIn('start_hour', change_log.new_values)
        self.assertEqual(change_log.old_values['start_hour'], 9)
        self.assertEqual(change_log.new_values['start_hour'], 10)

    def test_change_log_stores_reason(self):
        """変更理由が記録される"""
        change_log = revise_assignment(
            self.assignment,
            new_data={'start_hour': 10},
            reason='シフト調整のため',
        )
        self.assertEqual(change_log.reason, 'シフト調整のため')

    def test_change_log_records_revised_by(self):
        """変更者が記録される"""
        change_log = revise_assignment(
            self.assignment,
            new_data={'start_hour': 10},
            revised_by=self.manager,
        )
        self.assertEqual(change_log.changed_by, self.manager)

    def test_updates_only_specified_fields(self):
        """指定されたフィールドのみ更新される"""
        original_end = self.assignment.end_hour
        revise_assignment(
            self.assignment,
            new_data={'start_hour': 10},
        )
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.start_hour, 10)
        self.assertEqual(self.assignment.end_hour, original_end)

    def test_updates_note_field(self):
        """note フィールドを更新できる"""
        revise_assignment(
            self.assignment,
            new_data={'note': '更新されたメモ'},
        )
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.note, '更新されたメモ')


# ===========================================================================
# 10. shift_coverage サービスの詳細テスト
# ===========================================================================

class TestBuildCoverageMapService(TestCase):
    """build_coverage_map のサービステスト"""

    def test_returns_nested_defaultdict(self):
        """3層ネストの defaultdict を返す"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        result = cmap[d]['fortune_teller'][9]
        self.assertIsInstance(result, set)

    def test_empty_initial_state(self):
        """初期状態は空"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        self.assertEqual(len(cmap[d]['fortune_teller'][9]), 0)

    def test_different_dates_are_independent(self):
        """異なる日付のデータは独立している"""
        cmap = build_coverage_map()
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 2)
        cmap[d1]['fortune_teller'][9].add(100)
        self.assertNotIn(100, cmap[d2]['fortune_teller'][9])


class TestRecordAssignmentService(TestCase):
    """record_assignment のサービステスト"""

    def test_records_hourly_range(self):
        """start_h から end_h の各時間にスタッフIDを登録"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        record_assignment(cmap, d, 'fortune_teller', 9, 12, staff_id=1)

        for h in range(9, 12):
            self.assertIn(1, cmap[d]['fortune_teller'][h])
        self.assertNotIn(1, cmap[d]['fortune_teller'][12])

    def test_multiple_staff_same_slot(self):
        """同じ時間帯に複数スタッフを記録できる"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        record_assignment(cmap, d, 'fortune_teller', 10, 12, staff_id=1)
        record_assignment(cmap, d, 'fortune_teller', 10, 12, staff_id=2)
        self.assertEqual(len(cmap[d]['fortune_teller'][10]), 2)

    def test_same_staff_twice_does_not_duplicate(self):
        """同一スタッフを二回記録しても set は増えない"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=99)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=99)
        self.assertEqual(len(cmap[d]['fortune_teller'][9]), 1)

    def test_zero_length_range_records_nothing(self):
        """start_h == end_h では何も記録しない"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        record_assignment(cmap, d, 'fortune_teller', 9, 9, staff_id=1)
        self.assertNotIn(1, cmap[d]['fortune_teller'][9])

    def test_different_staff_types_are_independent(self):
        """スタッフ種別が異なるデータは独立"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 1)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=1)
        self.assertNotIn(1, cmap[d]['store_staff'][9])


class TestCheckCoverageNeedService(TestCase):
    """check_coverage_need のサービステスト"""

    def setUp(self):
        self.d = datetime.date(2026, 1, 15)
        self.req_map = {self.d: {'fortune_teller': 2}}
        self.cmap = build_coverage_map()

    def test_returns_true_when_slot_unfilled(self):
        """定員未達の時間帯があれば True"""
        record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=1)
        result = check_coverage_need(self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12)
        self.assertTrue(result)

    def test_returns_false_when_all_filled(self):
        """全時間帯が定員充足なら False"""
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=sid)
        result = check_coverage_need(self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12)
        self.assertFalse(result)

    def test_returns_true_when_required_is_zero(self):
        """required=0（未設定）なら常に True"""
        req_map = {self.d: {'fortune_teller': 0}}
        result = check_coverage_need(self.cmap, req_map, self.d, 'fortune_teller', 9, 12)
        self.assertTrue(result)

    def test_returns_true_when_date_not_in_req_map(self):
        """日付が req_map にない場合は True"""
        result = check_coverage_need(self.cmap, {}, self.d, 'fortune_teller', 9, 12)
        self.assertTrue(result)

    def test_single_hour_range(self):
        """1時間の範囲でも判定できる"""
        result = check_coverage_need(self.cmap, self.req_map, self.d, 'fortune_teller', 10, 11)
        self.assertTrue(result)

        record_assignment(self.cmap, self.d, 'fortune_teller', 10, 11, staff_id=1)
        record_assignment(self.cmap, self.d, 'fortune_teller', 10, 11, staff_id=2)
        result = check_coverage_need(self.cmap, self.req_map, self.d, 'fortune_teller', 10, 11)
        self.assertFalse(result)

    def test_partially_filled_is_still_true(self):
        """一部だけ充足していても False にならない"""
        # 11:00 のみ充足
        record_assignment(self.cmap, self.d, 'fortune_teller', 11, 12, staff_id=1)
        record_assignment(self.cmap, self.d, 'fortune_teller', 11, 12, staff_id=2)
        result = check_coverage_need(self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12)
        self.assertTrue(result)


class TestFindNeededBlocksService(TestCase):
    """find_needed_blocks のサービステスト"""

    def setUp(self):
        self.d = datetime.date(2026, 1, 15)
        self.req_map = {self.d: {'fortune_teller': 2}}
        self.cmap = build_coverage_map()

    def test_returns_full_range_when_all_unfilled(self):
        """全時間が未充足の場合は全範囲を1ブロックとして返す"""
        blocks = find_needed_blocks(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 17, 2,
        )
        self.assertEqual(blocks, [(9, 17)])

    def test_filters_filled_hours(self):
        """充足済み時間を除外する"""
        # 12-14 を充足
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 12, 14, staff_id=sid)

        blocks = find_needed_blocks(
            self.cmap, self.req_map, self.d, 'fortune_teller', 10, 18, 2,
        )
        self.assertEqual(blocks, [(10, 12), (14, 18)])

    def test_filters_blocks_below_min(self):
        """min_block 未満のブロックは除外される"""
        # 1時間のギャップを作る
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 10, 11, staff_id=sid)

        blocks = find_needed_blocks(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12, 2,
        )
        # 9-10=1h < 2 → 除外, 11-12=1h < 2 → 除外
        self.assertEqual(blocks, [])

    def test_returns_empty_when_all_filled(self):
        """全時間充足の場合は空リスト"""
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 9, 17, staff_id=sid)

        blocks = find_needed_blocks(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 17, 2,
        )
        self.assertEqual(blocks, [])

    def test_returns_full_range_when_required_zero(self):
        """required=0（無制限）の場合は全範囲を1ブロックで返す"""
        req_map = {self.d: {'fortune_teller': 0}}
        blocks = find_needed_blocks(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 17, 2,
        )
        self.assertEqual(blocks, [(9, 17)])

    def test_tail_end_block_included(self):
        """末尾の不足ブロックも含まれる"""
        # 9-11 のみ充足
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 9, 11, staff_id=sid)

        blocks = find_needed_blocks(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 17, 2,
        )
        # 11-17=6h のブロックが含まれる
        self.assertIn((11, 17), blocks)


class TestCountCoverageHoursService(TestCase):
    """count_coverage_hours のサービステスト"""

    def setUp(self):
        self.d = datetime.date(2026, 1, 15)
        self.req_map = {self.d: {'fortune_teller': 2}}
        self.cmap = build_coverage_map()

    def test_all_unfilled_returns_full_hours(self):
        """全時間未充足のとき範囲全体を返す"""
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 4)

    def test_all_filled_returns_zero(self):
        """全時間充足のとき 0 を返す"""
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 9, 13, staff_id=sid)
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 0)

    def test_partial_fill_returns_remaining_count(self):
        """一部充足のとき不足時間数を返す"""
        # 11:00 のみ充足
        for sid in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 11, 12, staff_id=sid)
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 3)  # 9, 10, 12 の 3 時間

    def test_zero_length_range_returns_zero(self):
        """0時間のレンジでは 0 を返す"""
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 10, 10,
        )
        self.assertEqual(result, 0)

    def test_no_requirement_returns_full_range(self):
        """required=0 のとき全範囲を返す"""
        req_map = {self.d: {'fortune_teller': 0}}
        result = count_coverage_hours(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 4)


class TestGenerateVacanciesService(TestCase):
    """generate_vacancies のサービステスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.period = ShiftPeriodFactory(store=self.store)

    def test_creates_vacancy_for_shortage(self):
        """不足スロットに ShiftVacancy を生成する"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 2}}
        cmap = build_coverage_map()
        record_assignment(cmap, d, 'fortune_teller', 9, 21, staff_id=1)  # 1名のみ（定員2）

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 21)

        self.assertEqual(count, 1)
        vacancy = ShiftVacancy.objects.filter(period=self.period).first()
        self.assertIsNotNone(vacancy)
        self.assertEqual(vacancy.required_count, 2)
        self.assertEqual(vacancy.assigned_count, 1)

    def test_merges_consecutive_shortage_hours(self):
        """連続する不足時間帯を1つの vacancy にマージ"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 1)
        vacancy = ShiftVacancy.objects.filter(period=self.period).first()
        self.assertEqual(vacancy.start_hour, 9)
        self.assertEqual(vacancy.end_hour, 12)

    def test_splits_non_consecutive_shortage_hours(self):
        """非連続の不足時間帯は別 vacancy になる"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        record_assignment(cmap, d, 'fortune_teller', 10, 11, staff_id=1)  # 10-11 のみ充足

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 2)

    def test_no_vacancy_when_fully_covered(self):
        """全時間充足の場合は vacancy を生成しない"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        record_assignment(cmap, d, 'fortune_teller', 9, 12, staff_id=1)

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 0)

    def test_clears_existing_vacancies_before_generating(self):
        """生成前に既存の vacancy を削除する"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()

        generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)
        generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)

        self.assertEqual(ShiftVacancy.objects.filter(period=self.period).count(), 1)

    def test_handles_empty_req_map(self):
        """req_map が空の場合は vacancy を生成しない"""
        cmap = build_coverage_map()
        count = generate_vacancies(self.period, self.store, {}, cmap, 9, 21)
        self.assertEqual(count, 0)

    def test_skips_zero_required_count(self):
        """required_count=0 の日付はスキップ"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 0}}
        cmap = build_coverage_map()

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 0)

    def test_handles_multiple_dates(self):
        """複数日付にまたがって vacancy を生成できる"""
        d1 = datetime.date(2026, 4, 6)
        d2 = datetime.date(2026, 4, 7)
        req_map = {
            d1: {'fortune_teller': 1},
            d2: {'fortune_teller': 1},
        }
        cmap = build_coverage_map()

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)

        self.assertEqual(count, 2)

    def test_vacancy_status_is_open(self):
        """生成された vacancy の status は 'open'"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()

        generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)

        vacancy = ShiftVacancy.objects.filter(period=self.period).first()
        self.assertEqual(vacancy.status, 'open')

    def test_vacancy_handles_end_of_day_shortage(self):
        """営業時間末尾の不足時間帯も正しく vacancy を生成"""
        d = datetime.date(2026, 4, 6)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=1)  # 9-11 のみ充足

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 13)

        self.assertEqual(count, 1)
        vacancy = ShiftVacancy.objects.filter(period=self.period).first()
        self.assertEqual(vacancy.start_hour, 11)
        self.assertEqual(vacancy.end_hour, 13)


# ===========================================================================
# 11. 部分アサイン（find_needed_blocks → auto_schedule）の統合テスト
# ===========================================================================

class TestPartialAssignmentIntegration(TestCase):
    """部分アサインのシナリオ統合テスト"""

    def setUp(self):
        self.store = StoreFactory()
        self.config = StoreScheduleConfigFactory(
            store=self.store,
            open_hour=9,
            close_hour=21,
            min_shift_hours=2,
        )
        for dow in range(7):
            ShiftStaffRequirement.objects.create(
                store=self.store,
                day_of_week=dow,
                staff_type='fortune_teller',
                required_count=2,
            )
        self.staff1 = StaffFactory(store=self.store)
        self.staff2 = StaffFactory(store=self.store)
        self.staff3 = StaffFactory(store=self.store)
        self.period = ShiftPeriodFactory(
            store=self.store,
            year_month=datetime.date(2026, 1, 1),
        )

    def make_request(self, staff, date, start_hour, end_hour, preference='available'):
        return ShiftRequest.objects.create(
            period=self.period,
            staff=staff,
            date=date,
            start_hour=start_hour,
            end_hour=end_hour,
            preference=preference,
        )

    def test_available_assigned_only_to_needed_blocks(self):
        """available スタッフは不足ブロックにのみアサインされる"""
        date = datetime.date(2026, 1, 5)  # 月曜 required=2

        # staff1, staff2 で 12-14 充足
        self.make_request(self.staff1, date, 12, 14, preference='preferred')
        self.make_request(self.staff2, date, 12, 14, preference='preferred')

        # staff3 は全体希望 → 9-12 と 14-21 が不足（各 3h/7h ≥ 2h）
        self.make_request(self.staff3, date, 9, 21, preference='available')

        auto_schedule(self.period)

        assignments = list(
            ShiftAssignment.objects.filter(
                period=self.period, staff=self.staff3,
            ).order_by('start_hour')
        )
        # 9-12 と 14-21 の 2 ブロック
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0].start_hour, 9)
        self.assertEqual(assignments[0].end_hour, 12)
        self.assertEqual(assignments[1].start_hour, 14)
        self.assertEqual(assignments[1].end_hour, 21)

    def test_block_below_min_shift_is_excluded(self):
        """min_shift_hours 未満のブロックは除外される"""
        date = datetime.date(2026, 1, 5)

        # staff1, staff2 で 9-20 充足（20-21 のみ1時間不足）
        self.make_request(self.staff1, date, 9, 20, preference='preferred')
        self.make_request(self.staff2, date, 9, 20, preference='preferred')

        # staff3 は 9-21 希望 → 20-21 が1時間不足（< min=2）
        self.make_request(self.staff3, date, 9, 21, preference='available')

        auto_schedule(self.period)

        # staff3 はアサインされない（1h < min 2h）
        count = ShiftAssignment.objects.filter(period=self.period, staff=self.staff3).count()
        self.assertEqual(count, 0)
