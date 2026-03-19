"""
shift scheduling 改善のテストスイート

テスト対象:
  - booking/services/shift_coverage.py (coverage helpers)
  - booking/services/shift_scheduler.py (auto_schedule)
  - booking/views_shift_api.py (vacancy & swap APIs)
  - booking/views_shift_staff.py (min-shift validation)
"""
import datetime
import json
from collections import defaultdict
from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from booking.models import (
    Store,
    Staff,
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    ShiftVacancy,
    ShiftSwapRequest,
    ShiftChangeLog,
    StoreScheduleConfig,
    StoreClosedDate,
    ShiftStaffRequirement,
)
from booking.services.shift_coverage import (
    build_coverage_map,
    record_assignment,
    check_coverage_need,
    count_coverage_hours,
    generate_vacancies,
)
from booking.services.shift_scheduler import auto_schedule


# ===========================================================================
# Helpers
# ===========================================================================

def make_user(username, is_staff=True, is_superuser=False):
    user = User.objects.create_user(
        username=username,
        password='testpass123',
        is_staff=is_staff,
        is_superuser=is_superuser,
    )
    return user


def make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def make_staff(user, store, name='テストスタッフ', staff_type='fortune_teller',
               is_store_manager=False):
    return Staff.objects.create(
        user=user,
        store=store,
        name=name,
        staff_type=staff_type,
        is_store_manager=is_store_manager,
    )


def make_config(store, open_hour=9, close_hour=21, min_shift_hours=2):
    return StoreScheduleConfig.objects.create(
        store=store,
        open_hour=open_hour,
        close_hour=close_hour,
        slot_duration=60,
        min_shift_hours=min_shift_hours,
    )


def make_period(store, year=2026, month=1, status='open'):
    return ShiftPeriod.objects.create(
        store=store,
        year_month=datetime.date(year, month, 1),
        status=status,
    )


def make_requirement(store, day_of_week, staff_type='fortune_teller', required_count=2):
    return ShiftStaffRequirement.objects.create(
        store=store,
        day_of_week=day_of_week,
        staff_type=staff_type,
        required_count=required_count,
    )


def make_request(period, staff, date, start_hour, end_hour, preference='available'):
    return ShiftRequest.objects.create(
        period=period,
        staff=staff,
        date=date,
        start_hour=start_hour,
        end_hour=end_hour,
        preference=preference,
    )


def make_assignment(period, staff, date, start_hour, end_hour):
    return ShiftAssignment.objects.create(
        period=period,
        staff=staff,
        date=date,
        start_hour=start_hour,
        end_hour=end_hour,
        start_time=datetime.time(start_hour, 0),
        end_time=datetime.time(end_hour % 24, 0),
    )


# ===========================================================================
# 1. shift_coverage.py ユニットテスト
# ===========================================================================

class TestBuildCoverageMap(TestCase):
    """build_coverage_map のテスト"""

    def test_returns_defaultdict_structure(self):
        """空のカバレッジマップが正しい構造で返される"""
        cmap = build_coverage_map()
        # defaultdict でキーが存在しないときも動作する
        d = datetime.date(2026, 1, 15)
        result = cmap[d]['fortune_teller'][9]
        self.assertIsInstance(result, set)
        self.assertEqual(len(result), 0)

    def test_nested_access_does_not_raise(self):
        """存在しないキーへのアクセスが例外なく動作する"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 3, 1)
        # 三重ネストのアクセスが KeyError を出さない
        _ = cmap[d]['store_staff'][14]

    def test_independent_dates(self):
        """異なる日付のエントリは独立している"""
        cmap = build_coverage_map()
        d1 = datetime.date(2026, 1, 1)
        d2 = datetime.date(2026, 1, 2)
        cmap[d1]['fortune_teller'][9].add(1)
        # d2 の 9 時には d1 のスタッフが含まれない
        self.assertNotIn(1, cmap[d2]['fortune_teller'][9])


class TestRecordAssignment(TestCase):
    """record_assignment のテスト"""

    def test_records_each_hour_in_range(self):
        """start_h から end_h の各時間にスタッフIDが登録される"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 10)
        record_assignment(cmap, d, 'fortune_teller', 9, 13, staff_id=42)
        for h in range(9, 13):
            self.assertIn(42, cmap[d]['fortune_teller'][h])
        # 範囲外は登録されていない
        self.assertNotIn(42, cmap[d]['fortune_teller'][13])
        self.assertNotIn(42, cmap[d]['fortune_teller'][8])

    def test_multiple_staff_same_hour(self):
        """同一時間帯に複数スタッフを記録できる"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 10)
        record_assignment(cmap, d, 'fortune_teller', 10, 12, staff_id=1)
        record_assignment(cmap, d, 'fortune_teller', 10, 12, staff_id=2)
        self.assertEqual(len(cmap[d]['fortune_teller'][10]), 2)
        self.assertIn(1, cmap[d]['fortune_teller'][10])
        self.assertIn(2, cmap[d]['fortune_teller'][10])

    def test_different_staff_types_are_independent(self):
        """異なるスタッフ種別のエントリは独立している"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 10)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=1)
        # store_staff の 9 時には登録されていない
        self.assertNotIn(1, cmap[d]['store_staff'][9])

    def test_zero_hour_range_records_nothing(self):
        """start_h == end_h のとき何も記録されない"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 1, 10)
        record_assignment(cmap, d, 'fortune_teller', 9, 9, staff_id=99)
        self.assertNotIn(99, cmap[d]['fortune_teller'][9])


class TestCheckCoverageNeed(TestCase):
    """check_coverage_need のテスト"""

    def setUp(self):
        self.d = datetime.date(2026, 1, 15)
        self.req_map = {self.d: {'fortune_teller': 2}}
        self.cmap = build_coverage_map()

    def test_returns_true_when_hours_are_unfilled(self):
        """定員に達していない時間帯があれば True を返す"""
        # 1 人だけ割当済み（定員 2）
        record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=1)
        result = check_coverage_need(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertTrue(result)

    def test_returns_false_when_all_hours_filled(self):
        """全時間帯が定員に達していれば False を返す"""
        record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=1)
        record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=2)
        result = check_coverage_need(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertFalse(result)

    def test_returns_true_when_required_count_zero(self):
        """required_count が 0（未設定）のときは常に True を返す"""
        req_map = {self.d: {'fortune_teller': 0}}
        result = check_coverage_need(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertTrue(result)

    def test_returns_true_when_date_not_in_req_map(self):
        """req_map に日付が存在しないとき（required=0 扱い）True を返す"""
        req_map = {}
        result = check_coverage_need(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertTrue(result)

    def test_partially_filled_returns_true(self):
        """一部の時間帯だけ充足していても False にならない"""
        # 10 時のみ 2 人アサイン、9 時は 0 人
        record_assignment(self.cmap, self.d, 'fortune_teller', 10, 11, staff_id=1)
        record_assignment(self.cmap, self.d, 'fortune_teller', 10, 11, staff_id=2)
        result = check_coverage_need(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertTrue(result)

    def test_staff_type_not_in_req_map_returns_true(self):
        """req_map にスタッフ種別が存在しないとき True を返す"""
        req_map = {self.d: {'store_staff': 2}}  # fortune_teller は未設定
        record_assignment(self.cmap, self.d, 'fortune_teller', 9, 12, staff_id=1)
        result = check_coverage_need(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 12,
        )
        self.assertTrue(result)


class TestCountCoverageHours(TestCase):
    """count_coverage_hours のテスト"""

    def setUp(self):
        self.d = datetime.date(2026, 1, 15)
        self.req_map = {self.d: {'fortune_teller': 2}}
        self.cmap = build_coverage_map()

    def test_all_unfilled_returns_full_range(self):
        """全時間帯が未充足のとき範囲全体を返す"""
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 4)

    def test_all_filled_returns_zero(self):
        """全時間帯が充足のとき 0 を返す"""
        for i in (1, 2):
            record_assignment(self.cmap, self.d, 'fortune_teller', 9, 13, staff_id=i)
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 0)

    def test_partial_fill_counts_remaining(self):
        """一部充足時は不足時間数だけ返す"""
        # 11 時のみ充足
        record_assignment(self.cmap, self.d, 'fortune_teller', 11, 12, staff_id=1)
        record_assignment(self.cmap, self.d, 'fortune_teller', 11, 12, staff_id=2)
        result = count_coverage_hours(
            self.cmap, self.req_map, self.d, 'fortune_teller', 9, 13,
        )
        # 9, 10, 12 の 3 時間が未充足
        self.assertEqual(result, 3)

    def test_no_limit_returns_full_range(self):
        """required_count=0 のとき全時間を返す"""
        req_map = {self.d: {'fortune_teller': 0}}
        result = count_coverage_hours(
            self.cmap, req_map, self.d, 'fortune_teller', 9, 13,
        )
        self.assertEqual(result, 4)


# ===========================================================================
# 2. generate_vacancies のテスト
# ===========================================================================

class TestGenerateVacancies(TestCase):
    """generate_vacancies のテスト"""

    def setUp(self):
        self.store = make_store('generate_test')
        self.user = make_user('gen_user')
        self.period = make_period(self.store, year=2026, month=1)

    def test_creates_vacancy_for_unfilled_slot(self):
        """未充足スロットに ShiftVacancy が生成される"""
        d = datetime.date(2026, 1, 6)  # 月曜
        req_map = {d: {'fortune_teller': 2}}
        cmap = build_coverage_map()
        # 1 人だけ割当済み（定員 2）
        record_assignment(cmap, d, 'fortune_teller', 9, 21, staff_id=1)

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 21)

        self.assertEqual(count, 1)
        vacancy = ShiftVacancy.objects.get(period=self.period)
        self.assertEqual(vacancy.start_hour, 9)
        self.assertEqual(vacancy.end_hour, 21)
        self.assertEqual(vacancy.required_count, 2)
        self.assertEqual(vacancy.assigned_count, 1)
        self.assertEqual(vacancy.status, 'open')

    def test_merges_consecutive_unfilled_hours(self):
        """連続する未充足時間帯は 1 つの vacancy にマージされる"""
        d = datetime.date(2026, 1, 7)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        # 誰もアサインされていない → 全時間帯未充足

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 1)
        v = ShiftVacancy.objects.filter(period=self.period).first()
        self.assertEqual(v.start_hour, 9)
        self.assertEqual(v.end_hour, 12)

    def test_splits_non_consecutive_unfilled_hours(self):
        """非連続の未充足時間帯は別々の vacancy になる"""
        d = datetime.date(2026, 1, 8)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        # 10 時のみ充足（9 と 11 が未充足）
        record_assignment(cmap, d, 'fortune_teller', 10, 11, staff_id=1)

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 2)
        vacancies = list(
            ShiftVacancy.objects.filter(period=self.period).order_by('start_hour')
        )
        self.assertEqual(vacancies[0].start_hour, 9)
        self.assertEqual(vacancies[0].end_hour, 10)
        self.assertEqual(vacancies[1].start_hour, 11)
        self.assertEqual(vacancies[1].end_hour, 12)

    def test_handles_end_of_day_unfilled_slot(self):
        """営業終了直前まで未充足の場合も vacancy を生成する"""
        d = datetime.date(2026, 1, 9)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        # 9-11 のみ充足
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=1)

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 13)

        self.assertEqual(count, 1)
        v = ShiftVacancy.objects.get(period=self.period)
        self.assertEqual(v.start_hour, 11)
        self.assertEqual(v.end_hour, 13)

    def test_no_vacancy_when_fully_covered(self):
        """全時間帯が充足済みのとき vacancy は生成されない"""
        d = datetime.date(2026, 1, 10)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        record_assignment(cmap, d, 'fortune_teller', 9, 12, staff_id=1)

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 0)
        self.assertEqual(ShiftVacancy.objects.filter(period=self.period).count(), 0)

    def test_deletes_existing_vacancies_before_generating(self):
        """再実行時は既存 vacancy を削除してから生成する"""
        d = datetime.date(2026, 1, 11)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()

        # 1 回目
        generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)
        self.assertEqual(ShiftVacancy.objects.filter(period=self.period).count(), 1)

        # 2 回目（同じ条件）
        generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)
        # 重複せず 1 件のまま
        self.assertEqual(ShiftVacancy.objects.filter(period=self.period).count(), 1)

    def test_skips_dates_with_zero_required(self):
        """required_count が 0 のとき vacancy を生成しない"""
        d = datetime.date(2026, 1, 12)
        req_map = {d: {'fortune_teller': 0}}
        cmap = build_coverage_map()

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 12)

        self.assertEqual(count, 0)

    def test_multiple_dates(self):
        """複数の日付を跨いで vacancy が生成される"""
        d1 = datetime.date(2026, 1, 13)
        d2 = datetime.date(2026, 1, 14)
        req_map = {
            d1: {'fortune_teller': 1},
            d2: {'fortune_teller': 1},
        }
        cmap = build_coverage_map()

        count = generate_vacancies(self.period, self.store, req_map, cmap, 9, 10)

        self.assertEqual(count, 2)


# ===========================================================================
# 3. auto_schedule のテスト
# ===========================================================================

class AutoScheduleBase(TestCase):
    """auto_schedule テストの共通セットアップ"""

    def setUp(self):
        self.store = make_store('auto_schedule_store')
        self.config = make_config(self.store, open_hour=9, close_hour=21, min_shift_hours=2)

        self.user1 = make_user('sched_user1')
        self.user2 = make_user('sched_user2')
        self.staff1 = make_staff(self.user1, self.store, name='スタッフ1')
        self.staff2 = make_staff(self.user2, self.store, name='スタッフ2')

        # 2026-01 のシフト期間
        self.period = make_period(self.store, year=2026, month=1)

        # 月曜〜日曜すべての曜日に fortune_teller 2 名必要と設定
        for dow in range(7):
            make_requirement(self.store, dow, 'fortune_teller', required_count=2)


class TestAutoScheduleBusinessHoursClipping(AutoScheduleBase):
    """営業時間クリップのテスト"""

    def test_clip_start_hour_to_open(self):
        """開始時間が営業開始前 → 営業開始時間にクリップされてアサイン"""
        # open=13, min_shift=2 なのでリクエスト 10-17 → clip 13-17 = 4h → OK
        self.config.open_hour = 13
        self.config.min_shift_hours = 2
        self.config.save()

        d = datetime.date(2026, 1, 5)  # 月曜
        make_request(self.period, self.staff1, d, 10, 17)

        auto_schedule(self.period)

        assignments = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1)
        self.assertEqual(assignments.count(), 1)
        a = assignments.first()
        self.assertEqual(a.start_hour, 13)
        self.assertEqual(a.end_hour, 17)

    def test_clip_end_hour_to_close(self):
        """終了時間が営業終了後 → 営業終了時間にクリップされてアサイン"""
        # close=23, リクエスト 20-25 → clip 20-23 = 3h > 2h min → OK
        self.config.close_hour = 23
        self.config.min_shift_hours = 2
        self.config.save()

        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 20, 25)

        auto_schedule(self.period)

        assignments = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1)
        self.assertEqual(assignments.count(), 1)
        a = assignments.first()
        self.assertEqual(a.start_hour, 20)
        self.assertEqual(a.end_hour, 23)

    def test_entirely_outside_business_hours_is_skipped(self):
        """営業時間外のリクエストは完全にスキップされる"""
        # open=13, close=21 なので 9:00-12:00 は対象外 (eff_start=13 >= eff_end=12)
        self.config.open_hour = 13
        self.config.close_hour = 21
        self.config.save()

        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 9, 12)

        auto_schedule(self.period)

        assignments = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1)
        self.assertEqual(assignments.count(), 0)


class TestAutoScheduleMinShiftHours(AutoScheduleBase):
    """最低シフト時間チェックのテスト"""

    def test_clipped_duration_less_than_min_is_skipped(self):
        """クリップ後の時間が min_shift_hours 未満 → スキップ"""
        # open=9, close=21, min_shift=3
        # リクエスト: 8:00-10:00 → クリップ後 9:00-10:00 = 1h < 3h → skip
        self.config.open_hour = 9
        self.config.min_shift_hours = 3
        self.config.save()

        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 8, 10)

        auto_schedule(self.period)

        assignments = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1)
        self.assertEqual(assignments.count(), 0)

    def test_clipped_duration_equal_to_min_is_assigned(self):
        """クリップ後の時間がちょうど min_shift_hours → アサインされる"""
        # open=9, close=21, min_shift=3
        # リクエスト: 8:00-12:00 → クリップ後 9:00-12:00 = 3h = 3h → OK
        self.config.open_hour = 9
        self.config.min_shift_hours = 3
        self.config.save()

        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 8, 12)

        auto_schedule(self.period)

        assignments = ShiftAssignment.objects.filter(period=self.period, staff=self.staff1)
        self.assertEqual(assignments.count(), 1)
        self.assertEqual(assignments.first().start_hour, 9)
        self.assertEqual(assignments.first().end_hour, 12)


class TestAutoScheduleCoverage(AutoScheduleBase):
    """カバレッジベースのスケジューリングテスト"""

    def test_available_skipped_when_all_hours_covered(self):
        """定員 2 に対して 2 名 preferred 確定済み → available はスキップ"""
        d = datetime.date(2026, 1, 5)  # 月曜（required=2）
        extra_user3 = make_user('extra_user_cov3')
        staff3 = make_staff(extra_user3, self.store, name='追加スタッフ3')

        # preferred 2 名 (staff1, staff2)
        make_request(self.period, self.staff1, d, 9, 17, preference='preferred')
        make_request(self.period, self.staff2, d, 9, 17, preference='preferred')
        # available 1 名 (staff3)
        make_request(self.period, staff3, d, 9, 17, preference='available')

        auto_schedule(self.period)

        # staff3 はアサインされない
        self.assertEqual(
            ShiftAssignment.objects.filter(period=self.period, staff=staff3).count(),
            0,
        )

    def test_available_assigned_when_coverage_not_full(self):
        """定員 2 で 1 名のみ確定 → available もアサインされる"""
        d = datetime.date(2026, 1, 5)
        # preferred 1 名
        make_request(self.period, self.staff1, d, 9, 17, preference='preferred')
        # available 1 名
        make_request(self.period, self.staff2, d, 9, 17, preference='available')

        auto_schedule(self.period)

        self.assertEqual(
            ShiftAssignment.objects.filter(period=self.period, staff=self.staff2).count(),
            1,
        )

    def test_preferred_assigned_even_when_coverage_full(self):
        """定員 2 が満たされていても preferred はアサインされる"""
        d = datetime.date(2026, 1, 5)
        extra_user3 = make_user('pref_extra_user3')
        staff3 = make_staff(extra_user3, self.store, name='preferred追加スタッフ')

        # available 2 名で定員充足
        make_request(self.period, self.staff1, d, 9, 17, preference='available')
        make_request(self.period, self.staff2, d, 9, 17, preference='available')
        # preferred 1 名
        make_request(self.period, staff3, d, 9, 17, preference='preferred')

        auto_schedule(self.period)

        # staff3 (preferred) はアサインされる
        self.assertEqual(
            ShiftAssignment.objects.filter(period=self.period, staff=staff3).count(),
            1,
        )

    def test_closed_dates_are_skipped(self):
        """休業日のリクエストはスキップされる"""
        d = datetime.date(2026, 1, 5)
        StoreClosedDate.objects.create(store=self.store, date=d, reason='臨時休業')
        make_request(self.period, self.staff1, d, 9, 17)

        auto_schedule(self.period)

        self.assertEqual(
            ShiftAssignment.objects.filter(period=self.period).count(),
            0,
        )

    def test_duplicate_staff_slot_is_skipped(self):
        """auto_schedule を 2 回実行しても同一スタッフスロットが重複しない"""
        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 9, 17)
        auto_schedule(self.period)

        count_after_first = ShiftAssignment.objects.filter(
            period=self.period, staff=self.staff1,
        ).count()
        self.assertEqual(count_after_first, 1)

        # 再度 auto_schedule を実行しても同一スロットが 2 件にならない
        # （auto_schedule は既存アサイン全削除後に再生成するため 1 件のまま）
        auto_schedule(self.period)
        count_after_second = ShiftAssignment.objects.filter(
            period=self.period, staff=self.staff1,
        ).count()
        self.assertEqual(count_after_second, 1)

    def test_vacancies_generated_after_scheduling(self):
        """auto_schedule 後に未充足スロットの vacancy が生成される"""
        d = datetime.date(2026, 1, 5)  # 月曜（required=2）
        # 1 人だけアサイン
        make_request(self.period, self.staff1, d, 9, 21, preference='available')

        auto_schedule(self.period)

        # 1 名のみ割当、定員 2 なので vacancy が存在するはず
        vacancies = ShiftVacancy.objects.filter(period=self.period)
        self.assertGreater(vacancies.count(), 0)

    def test_period_status_set_to_scheduled(self):
        """auto_schedule 後に period.status が scheduled になる"""
        auto_schedule(self.period)
        self.period.refresh_from_db()
        self.assertEqual(self.period.status, 'scheduled')

    def test_unavailable_requests_are_excluded(self):
        """unavailable のリクエストは無視されアサインされない"""
        d = datetime.date(2026, 1, 5)
        make_request(self.period, self.staff1, d, 9, 17, preference='unavailable')

        auto_schedule(self.period)

        self.assertEqual(
            ShiftAssignment.objects.filter(period=self.period, staff=self.staff1).count(),
            0,
        )


# ===========================================================================
# 4. ShiftVacancyAPIView テスト
# ===========================================================================

class TestShiftVacancyAPIView(TestCase):
    """ShiftVacancyAPIView (GET: 不足枠一覧) のテスト"""

    def setUp(self):
        self.store = make_store('vacancy_store')
        self.manager_user = make_user('vacancy_manager', is_staff=True)
        self.manager = make_staff(
            self.manager_user, self.store,
            name='店長', is_store_manager=True,
        )
        self.period = make_period(self.store)
        self.client = Client()
        # staff_member_required は is_staff=True のユーザーを要求する
        self.client.force_login(self.manager_user)

        self.vacancy_url = '/api/shift/vacancies/'

    def _create_vacancy(self, date, start_hour=9, end_hour=17,
                        staff_type='fortune_teller', required=2, assigned=1):
        return ShiftVacancy.objects.create(
            period=self.period,
            store=self.store,
            date=date,
            start_hour=start_hour,
            end_hour=end_hour,
            staff_type=staff_type,
            required_count=required,
            assigned_count=assigned,
            status='open',
        )

    def test_get_returns_open_vacancies(self):
        """GET リクエストが open 状態の vacancy 一覧を返す"""
        self._create_vacancy(datetime.date(2026, 1, 5))
        resp = self.client.get(self.vacancy_url)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        data = body['results']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['status'], 'open')
        self.assertEqual(body['total'], 1)

    def test_get_filters_by_period_id(self):
        """period_id フィルターが機能する"""
        other_period = make_period(self.store, year=2026, month=2)
        self._create_vacancy(datetime.date(2026, 1, 5))
        ShiftVacancy.objects.create(
            period=other_period,
            store=self.store,
            date=datetime.date(2026, 2, 5),
            start_hour=9,
            end_hour=17,
            staff_type='fortune_teller',
            required_count=1,
            assigned_count=0,
            status='open',
        )

        resp = self.client.get(self.vacancy_url, {'period_id': self.period.id})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)['results']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['period_id'], self.period.id)

    def test_get_filters_by_staff_type(self):
        """staff_type フィルターが機能する"""
        self._create_vacancy(datetime.date(2026, 1, 5), staff_type='fortune_teller')
        self._create_vacancy(datetime.date(2026, 1, 5), staff_type='store_staff')

        resp = self.client.get(self.vacancy_url, {'staff_type': 'fortune_teller'})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)['results']
        self.assertTrue(all(v['staff_type'] == 'fortune_teller' for v in data))

    def test_shortage_property_in_response(self):
        """shortage フィールドが正しく計算されている"""
        self._create_vacancy(datetime.date(2026, 1, 5), required=3, assigned=1)
        resp = self.client.get(self.vacancy_url)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)['results']
        self.assertEqual(data[0]['shortage'], 2)


# ===========================================================================
# 5. ShiftVacancyApplyAPIView テスト
# ===========================================================================

class TestShiftVacancyApplyAPIView(TestCase):
    """ShiftVacancyApplyAPIView (POST: 不足枠応募) のテスト"""

    def setUp(self):
        self.store = make_store('apply_store')
        self.config = make_config(self.store)

        self.applicant_user = make_user('applicant', is_staff=True)
        self.applicant = make_staff(
            self.applicant_user, self.store,
            name='応募者', staff_type='fortune_teller',
        )

        self.period = make_period(self.store)
        self.vacancy = ShiftVacancy.objects.create(
            period=self.period,
            store=self.store,
            date=datetime.date(2026, 1, 10),
            start_hour=9,
            end_hour=17,
            staff_type='fortune_teller',
            required_count=2,
            assigned_count=1,
            status='open',
        )

        self.client = Client()
        self.client.force_login(self.applicant_user)

    def _apply_url(self, pk):
        return f'/api/shift/vacancies/{pk}/apply/'

    def test_apply_creates_shift_request(self):
        """応募すると ShiftRequest が生成される"""
        resp = self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        req = ShiftRequest.objects.filter(
            period=self.period,
            staff=self.applicant,
            date=self.vacancy.date,
        ).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.preference, 'preferred')

    def test_apply_rejects_wrong_staff_type(self):
        """スタッフ種別が一致しない場合は 400 を返す"""
        wrong_user = make_user('wrong_type_user', is_staff=True)
        make_staff(
            wrong_user, self.store,
            name='ストアスタッフ', staff_type='store_staff',
        )
        self.client.force_login(wrong_user)

        resp = self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn('スタッフ種別', data['error'])

    def test_apply_rejects_closed_vacancy(self):
        """filled 状態の vacancy への応募は 400 を返す"""
        self.vacancy.status = 'filled'
        self.vacancy.save()

        resp = self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_apply_rejects_duplicate_application(self):
        """同一日時への重複応募は 409 を返す"""
        # 1 回目
        self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        # 2 回目
        resp = self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 409)

    def test_apply_rejects_different_store_staff(self):
        """別店舗スタッフからの応募は 403 を返す"""
        other_store = make_store('other_apply_store')
        other_user = make_user('other_apply_user', is_staff=True)
        make_staff(
            other_user, other_store,
            name='他店スタッフ', staff_type='fortune_teller',
        )
        self.client.force_login(other_user)

        resp = self.client.post(
            self._apply_url(self.vacancy.pk),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 403)


# ===========================================================================
# 6. ShiftSwapRequestAPIView テスト
# ===========================================================================

class TestShiftSwapRequestAPIView(TestCase):
    """ShiftSwapRequestAPIView のテスト"""

    def setUp(self):
        self.store = make_store('swap_store')

        self.requester_user = make_user('swap_requester', is_staff=True)
        self.requester = make_staff(
            self.requester_user, self.store,
            name='申請スタッフ', staff_type='fortune_teller',
        )

        self.cover_user = make_user('cover_staff_user', is_staff=True)
        self.cover_staff = make_staff(
            self.cover_user, self.store,
            name='交代スタッフ', staff_type='fortune_teller',
        )

        self.manager_user = make_user('swap_manager', is_staff=True)
        self.manager = make_staff(
            self.manager_user, self.store,
            name='店長', is_store_manager=True,
        )

        self.period = make_period(self.store, status='scheduled')
        self.assignment = make_assignment(
            self.period, self.requester,
            datetime.date(2026, 1, 15), 9, 17,
        )

        self.client = Client()
        self.client.force_login(self.requester_user)

        self.create_url = '/api/shift/swap-requests/'

    def _approve_url(self, pk):
        return f'/api/shift/swap-requests/{pk}/'

    def test_create_swap_request(self):
        """交代申請を作成できる（LINE 通知はモック）"""
        with patch('booking.services.shift_notifications.notify_swap_request'):
            resp = self.client.post(
                self.create_url,
                data=json.dumps({
                    'assignment_id': self.assignment.pk,
                    'request_type': 'swap',
                    'reason': '私用のため',
                    'cover_staff_id': self.cover_staff.pk,
                }),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 201)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'pending')

    def test_create_absence_request(self):
        """欠勤申請を作成できる"""
        with patch('booking.services.shift_notifications.notify_swap_request'):
            resp = self.client.post(
                self.create_url,
                data=json.dumps({
                    'assignment_id': self.assignment.pk,
                    'request_type': 'absence',
                    'reason': '体調不良',
                }),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 201)

    def test_create_invalid_request_type_returns_400(self):
        """無効な request_type は 400 を返す"""
        resp = self.client.post(
            self.create_url,
            data=json.dumps({
                'assignment_id': self.assignment.pk,
                'request_type': 'invalid_type',
                'reason': 'test',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_approve_absence_deletes_assignment_and_creates_vacancy(self):
        """欠勤申請を承認すると assignment が削除され vacancy が生成される"""
        swap_req = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='absence',
            requested_by=self.requester,
            reason='体調不良',
        )

        self.client.force_login(self.manager_user)
        with patch('booking.services.shift_notifications.notify_swap_approved'), \
             patch('booking.services.shift_notifications.notify_emergency_cover'):
            resp = self.client.put(
                self._approve_url(swap_req.pk),
                data=json.dumps({'status': 'approved'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)

        # assignment が削除されている
        self.assertFalse(
            ShiftAssignment.objects.filter(pk=self.assignment.pk).exists()
        )
        # vacancy が生成されている
        vacancy = ShiftVacancy.objects.filter(
            period=self.period, date=self.assignment.date,
        ).first()
        self.assertIsNotNone(vacancy)
        self.assertEqual(vacancy.start_hour, self.assignment.start_hour)
        self.assertEqual(vacancy.end_hour, self.assignment.end_hour)
        self.assertEqual(vacancy.status, 'open')

    def test_approve_swap_transfers_assignment(self):
        """交代申請を承認すると cover_staff にアサインが移る"""
        swap_req = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='swap',
            requested_by=self.requester,
            cover_staff=self.cover_staff,
            reason='旅行',
        )

        self.client.force_login(self.manager_user)
        with patch('booking.services.shift_notifications.notify_swap_approved'):
            resp = self.client.put(
                self._approve_url(swap_req.pk),
                data=json.dumps({'status': 'approved'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)

        # 元のアサインは削除
        self.assertFalse(
            ShiftAssignment.objects.filter(pk=self.assignment.pk).exists()
        )
        # cover_staff にアサインが作成されている
        new_assign = ShiftAssignment.objects.filter(
            period=self.period,
            staff=self.cover_staff,
            date=self.assignment.date,
        ).first()
        self.assertIsNotNone(new_assign)

        # ShiftChangeLog が記録されている
        log = ShiftChangeLog.objects.filter(assignment=new_assign).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.old_values.get('staff_id'), self.requester.id)
        self.assertEqual(log.new_values.get('staff_id'), self.cover_staff.id)

    def test_reject_swap_request(self):
        """却下された申請の status が rejected になる"""
        swap_req = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='absence',
            requested_by=self.requester,
            reason='テスト',
        )

        self.client.force_login(self.manager_user)
        with patch('booking.services.shift_notifications.notify_swap_approved'):
            resp = self.client.put(
                self._approve_url(swap_req.pk),
                data=json.dumps({'status': 'rejected'}),
                content_type='application/json',
            )
        self.assertEqual(resp.status_code, 200)
        swap_req.refresh_from_db()
        self.assertEqual(swap_req.status, 'rejected')
        # assignment は残っている
        self.assertTrue(
            ShiftAssignment.objects.filter(pk=self.assignment.pk).exists()
        )

    def test_cannot_approve_already_processed_request(self):
        """処理済みの申請を再承認しようとすると 400 を返す"""
        swap_req = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='absence',
            requested_by=self.requester,
            reason='テスト',
            status='rejected',
        )

        self.client.force_login(self.manager_user)
        resp = self.client.put(
            self._approve_url(swap_req.pk),
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_get_swap_requests_returns_list(self):
        """GET で申請一覧が返される（マネージャーは全件閲覧可）"""
        ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='absence',
            requested_by=self.requester,
            reason='test',
        )
        self.client.force_login(self.manager_user)
        resp = self.client.get(self.create_url)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertEqual(body['total'], 1)
        self.assertEqual(len(body['results']), 1)


# ===========================================================================
# 7. StaffShiftRequestAPIView — 最低シフト時間バリデーション
# ===========================================================================

class TestStaffShiftRequestMinHoursValidation(TestCase):
    """StaffShiftRequestAPIView の最低シフト時間バリデーションテスト"""

    def setUp(self):
        self.store = make_store('min_shift_store')
        self.config = make_config(self.store, open_hour=9, close_hour=21, min_shift_hours=3)

        self.staff_user = make_user('min_shift_user', is_staff=True)
        self.staff = make_staff(self.staff_user, self.store, name='シフトスタッフ')

        self.period = make_period(self.store)
        self.client = Client()
        self.client.force_login(self.staff_user)

        self.url = '/api/shift/my-requests/'

    def _post_request(self, start_hour, end_hour, preference='available'):
        return self.client.post(
            self.url,
            data=json.dumps({
                'date': '2026-01-05',
                'start_hour': start_hour,
                'end_hour': end_hour,
                'preference': preference,
                'period_id': self.period.pk,
            }),
            content_type='application/json',
        )

    def test_rejects_shift_shorter_than_min_hours(self):
        """min_shift_hours=3 で 2 時間シフトは 400 を返す"""
        resp = self._post_request(9, 11)
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertIn('最低', data['error'])

    def test_rejects_shift_of_one_hour(self):
        """1 時間シフトは min_shift_hours=3 なので拒否される"""
        resp = self._post_request(10, 11)
        self.assertEqual(resp.status_code, 400)

    def test_accepts_shift_equal_to_min_hours(self):
        """ちょうど min_shift_hours (3 時間) は受け入れられる"""
        resp = self._post_request(9, 12)
        self.assertIn(resp.status_code, (200, 201))

    def test_accepts_shift_longer_than_min_hours(self):
        """min_shift_hours 以上のシフトは受け入れられる"""
        resp = self._post_request(9, 17)
        self.assertIn(resp.status_code, (200, 201))

    def test_unavailable_preference_bypasses_min_hours_check(self):
        """preference=unavailable は最低時間チェックをバイパスする"""
        resp = self._post_request(9, 10, preference='unavailable')
        # unavailable は長さに関係なく受け入れられる
        self.assertIn(resp.status_code, (200, 201))

    def test_default_min_hours_when_no_config(self):
        """StoreScheduleConfig がない場合はデフォルト 2 時間が適用される"""
        no_config_store = make_store('no_config_store')
        no_config_user = make_user('no_config_user', is_staff=True)
        make_staff(no_config_user, no_config_store, name='ノーコンフィグスタッフ')
        no_config_period = make_period(no_config_store)

        client = Client()
        client.force_login(no_config_user)

        # 1 時間 → デフォルト min=2 なので拒否
        resp = client.post(
            self.url,
            data=json.dumps({
                'date': '2026-01-05',
                'start_hour': 9,
                'end_hour': 10,
                'preference': 'available',
                'period_id': no_config_period.pk,
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

        # 2 時間 → デフォルト min=2 なので OK
        resp = client.post(
            self.url,
            data=json.dumps({
                'date': '2026-01-05',
                'start_hour': 9,
                'end_hour': 11,
                'preference': 'available',
                'period_id': no_config_period.pk,
            }),
            content_type='application/json',
        )
        self.assertIn(resp.status_code, (200, 201))


# ===========================================================================
# 8. 境界値・エッジケーステスト
# ===========================================================================

class TestEdgeCases(TestCase):
    """境界値・エッジケース"""

    def test_check_coverage_need_single_hour_range(self):
        """1 時間のレンジでも正しく判定できる"""
        d = datetime.date(2026, 2, 1)
        req_map = {d: {'fortune_teller': 1}}
        cmap = build_coverage_map()
        # 未アサイン
        self.assertTrue(
            check_coverage_need(cmap, req_map, d, 'fortune_teller', 10, 11)
        )
        # アサイン後
        record_assignment(cmap, d, 'fortune_teller', 10, 11, staff_id=1)
        self.assertFalse(
            check_coverage_need(cmap, req_map, d, 'fortune_teller', 10, 11)
        )

    def test_record_assignment_with_same_staff_twice(self):
        """同一スタッフを同じ時間帯に 2 回記録しても set は増えない"""
        cmap = build_coverage_map()
        d = datetime.date(2026, 2, 1)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=99)
        record_assignment(cmap, d, 'fortune_teller', 9, 11, staff_id=99)
        self.assertEqual(len(cmap[d]['fortune_teller'][9]), 1)

    def test_generate_vacancies_empty_req_map(self):
        """req_map が空のとき vacancy は生成されない"""
        store = make_store('edge_store')
        make_user('edge_user')
        period = make_period(store)
        cmap = build_coverage_map()

        count = generate_vacancies(period, store, {}, cmap, 9, 21)
        self.assertEqual(count, 0)

    def test_auto_schedule_no_requests(self):
        """リクエストが 0 件でも auto_schedule はエラーにならない"""
        store = make_store('empty_store')
        make_config(store)
        period = make_period(store, year=2026, month=2)

        result = auto_schedule(period)

        self.assertEqual(result, 0)
        period.refresh_from_db()
        self.assertEqual(period.status, 'scheduled')

    def test_count_coverage_hours_zero_length_range(self):
        """0 時間のレンジでは 0 を返す"""
        d = datetime.date(2026, 2, 15)
        cmap = build_coverage_map()
        req_map = {d: {'fortune_teller': 1}}
        result = count_coverage_hours(cmap, req_map, d, 'fortune_teller', 10, 10)
        self.assertEqual(result, 0)

    def test_vacancy_shortage_property(self):
        """ShiftVacancy.shortage プロパティが正しく計算される"""
        store = make_store('shortage_store')
        period = make_period(store)
        v = ShiftVacancy.objects.create(
            period=period,
            store=store,
            date=datetime.date(2026, 1, 5),
            start_hour=9,
            end_hour=17,
            staff_type='fortune_teller',
            required_count=3,
            assigned_count=1,
            status='open',
        )
        self.assertEqual(v.shortage, 2)

    def test_vacancy_shortage_zero_when_fully_covered(self):
        """assigned >= required のとき shortage は 0"""
        store = make_store('shortage_zero_store')
        period = make_period(store)
        v = ShiftVacancy.objects.create(
            period=period,
            store=store,
            date=datetime.date(2026, 1, 5),
            start_hour=9,
            end_hour=17,
            staff_type='fortune_teller',
            required_count=2,
            assigned_count=3,
            status='open',
        )
        self.assertEqual(v.shortage, 0)
