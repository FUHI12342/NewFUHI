"""
シフト品質改善のテストスイート

テスト対象:
  - booking/validators.py (共通バリデーション)
  - booking/api_response.py (統一レスポンスヘルパー)
  - booking/views_shift_vacancy_api.py (競合チェック, vacancy充足)
  - booking/services/shift_scheduler.py (撤回時ChangeLog, timezone)
  - booking/views_shift_api.py (ChangeLog API)
  - booking/models/core.py (Store.timezone)
"""
import datetime
import json

from django.contrib.auth.models import User
from django.test import TestCase, Client

from booking.models import (
    Store, Staff, ShiftPeriod, ShiftAssignment,
    ShiftVacancy, ShiftSwapRequest, ShiftChangeLog,
    StoreScheduleConfig, StoreClosedDate,
)
from booking.validators import (
    validate_hour_range, validate_preference, validate_min_shift,
    validate_closed_date, validate_business_hours, truncate_note,
    validate_color,
)
from booking.api_response import success_response, error_response, list_response


# ===========================================================================
# Helpers
# ===========================================================================

def make_user(username, is_staff=True, is_superuser=False):
    return User.objects.create_user(
        username=username, password='testpass123',
        is_staff=is_staff, is_superuser=is_superuser,
    )


def make_store(name='テスト店舗'):
    return Store.objects.create(name=name)


def make_staff(user, store, name='テストスタッフ', staff_type='fortune_teller',
               is_store_manager=False):
    return Staff.objects.create(
        user=user, store=store, name=name,
        staff_type=staff_type, is_store_manager=is_store_manager,
    )


def make_config(store, open_hour=9, close_hour=21, min_shift_hours=2):
    return StoreScheduleConfig.objects.create(
        store=store, open_hour=open_hour, close_hour=close_hour,
        slot_duration=60, min_shift_hours=min_shift_hours,
    )


# ===========================================================================
# 1. Validators テスト
# ===========================================================================

class ValidateHourRangeTest(TestCase):
    def test_valid_range(self):
        s, e, err = validate_hour_range({'start_hour': 9, 'end_hour': 17})
        self.assertEqual(s, 9)
        self.assertEqual(e, 17)
        self.assertIsNone(err)

    def test_invalid_range_start_gte_end(self):
        _, _, err = validate_hour_range({'start_hour': 17, 'end_hour': 9})
        self.assertIsNotNone(err)

    def test_invalid_type(self):
        _, _, err = validate_hour_range({'start_hour': 'abc', 'end_hour': 17})
        self.assertIsNotNone(err)

    def test_boundary_values(self):
        s, e, err = validate_hour_range({'start_hour': 0, 'end_hour': 24})
        self.assertEqual(s, 0)
        self.assertEqual(e, 24)
        self.assertIsNone(err)

    def test_start_hour_24_invalid(self):
        _, _, err = validate_hour_range({'start_hour': 24, 'end_hour': 24})
        self.assertIsNotNone(err)


class ValidateMinShiftTest(TestCase):
    def test_min_shift_check_passes(self):
        store = make_store()
        make_config(store, min_shift_hours=3)
        result, err = validate_min_shift(store, 9, 12)
        self.assertEqual(result, 3)
        self.assertIsNone(err)

    def test_min_shift_check_fails(self):
        store = make_store()
        make_config(store, min_shift_hours=3)
        _, err = validate_min_shift(store, 9, 10)
        self.assertIn('3時間', err)

    def test_unavailable_skips_check(self):
        store = make_store()
        make_config(store, min_shift_hours=8)
        result, err = validate_min_shift(store, 9, 10, preference='unavailable')
        self.assertIsNone(result)
        self.assertIsNone(err)

    def test_default_min_shift_without_config(self):
        store = make_store()
        result, err = validate_min_shift(store, 9, 11)
        self.assertEqual(result, 2)
        self.assertIsNone(err)


class ValidateClosedDateTest(TestCase):
    def test_closed_date_returns_error(self):
        store = make_store()
        d = datetime.date(2026, 4, 1)
        StoreClosedDate.objects.create(store=store, date=d)
        err = validate_closed_date(store, d)
        self.assertIn('休業日', err)

    def test_open_date_returns_none(self):
        store = make_store()
        d = datetime.date(2026, 4, 2)
        err = validate_closed_date(store, d)
        self.assertIsNone(err)


class TruncateNoteTest(TestCase):
    def test_short_note_unchanged(self):
        self.assertEqual(truncate_note('hello'), 'hello')

    def test_long_note_truncated(self):
        long = 'x' * 600
        result = truncate_note(long)
        self.assertEqual(len(result), 500)

    def test_none_returns_empty(self):
        self.assertEqual(truncate_note(None), '')

    def test_custom_max_length(self):
        self.assertEqual(len(truncate_note('x' * 20, max_length=10)), 10)


class ValidateColorTest(TestCase):
    def test_valid_color(self):
        self.assertEqual(validate_color('#3B82F6'), '#3B82F6')

    def test_invalid_color(self):
        self.assertIsNone(validate_color('#ZZZ'))
        self.assertIsNone(validate_color('red'))
        self.assertIsNone(validate_color(None))


class ValidateBusinessHoursTest(TestCase):
    def test_within_hours(self):
        self.assertIsNone(validate_business_hours(10, 18, 9, 21))

    def test_outside_hours(self):
        err = validate_business_hours(8, 22, 9, 21)
        self.assertIn('営業時間', err)


class ValidatePreferenceTest(TestCase):
    def test_valid(self):
        self.assertIsNone(validate_preference('available'))
        self.assertIsNone(validate_preference('preferred'))
        self.assertIsNone(validate_preference('unavailable'))

    def test_invalid(self):
        self.assertIsNotNone(validate_preference('maybe'))


# ===========================================================================
# 2. API Response テスト
# ===========================================================================

class SuccessResponseTest(TestCase):
    def test_format(self):
        resp = success_response({'id': 1})
        body = json.loads(resp.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['id'], 1)
        self.assertEqual(resp.status_code, 200)

    def test_custom_status(self):
        resp = success_response({'id': 1}, status=201)
        self.assertEqual(resp.status_code, 201)

    def test_with_meta(self):
        resp = success_response({'id': 1}, meta={'page': 1})
        body = json.loads(resp.content)
        self.assertEqual(body['meta']['page'], 1)


class ErrorResponseTest(TestCase):
    def test_format(self):
        resp = error_response('bad input')
        body = json.loads(resp.content)
        self.assertFalse(body['success'])
        self.assertEqual(body['error'], 'bad input')
        self.assertEqual(resp.status_code, 400)

    def test_custom_status_and_code(self):
        resp = error_response('conflict', status=409, code='CONFLICT')
        body = json.loads(resp.content)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(body['code'], 'CONFLICT')


class ListResponseTest(TestCase):
    def test_format(self):
        resp = list_response([{'id': 1}], total=1, limit=10)
        body = json.loads(resp.content)
        self.assertTrue(body['success'])
        self.assertEqual(body['data']['total'], 1)
        self.assertEqual(body['data']['results'], [{'id': 1}])
        self.assertEqual(body['data']['limit'], 10)


# ===========================================================================
# 3. Swap 競合チェックテスト
# ===========================================================================

class SwapConflictCheckTest(TestCase):
    def setUp(self):
        self.store = make_store()
        self.manager_user = make_user('manager1')
        self.manager = make_staff(
            self.manager_user, self.store, 'マネージャー',
            is_store_manager=True,
        )
        self.staff_a_user = make_user('staff_a')
        self.staff_a = make_staff(self.staff_a_user, self.store, 'スタッフA')
        self.cover_user = make_user('cover_staff')
        self.cover_staff = make_staff(self.cover_user, self.store, 'カバースタッフ')
        self.period = ShiftPeriod.objects.create(
            store=self.store, year_month=datetime.date(2026, 4, 1),
            status='approved',
        )
        self.assignment = ShiftAssignment.objects.create(
            period=self.period, staff=self.staff_a,
            date=datetime.date(2026, 4, 10),
            start_hour=10, end_hour=18,
        )
        self.client = Client()
        self.client.login(username='manager1', password='testpass123')

    def test_conflict_blocks_approval(self):
        # cover_staff has existing assignment at overlapping time
        ShiftAssignment.objects.create(
            period=self.period, staff=self.cover_staff,
            date=datetime.date(2026, 4, 10),
            start_hour=12, end_hour=16,
        )
        swap = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='swap',
            requested_by=self.staff_a,
            cover_staff=self.cover_staff,
            reason='テスト',
        )
        resp = self.client.put(
            f'/api/shift/swap-requests/{swap.pk}/',
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 409)
        body = json.loads(resp.content)
        self.assertEqual(body['code'], 'SCHEDULE_CONFLICT')

    def test_no_conflict_allows_approval(self):
        swap = ShiftSwapRequest.objects.create(
            assignment=self.assignment,
            request_type='swap',
            requested_by=self.staff_a,
            cover_staff=self.cover_staff,
            reason='テスト',
        )
        resp = self.client.put(
            f'/api/shift/swap-requests/{swap.pk}/',
            data=json.dumps({'status': 'approved'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertTrue(body['success'])


# ===========================================================================
# 4. Vacancy 自動充足テスト
# ===========================================================================

class VacancyAutoFillTest(TestCase):
    def setUp(self):
        self.store = make_store()
        self.user = make_user('staff1')
        self.staff = make_staff(self.user, self.store, 'スタッフ1')
        self.period = ShiftPeriod.objects.create(
            store=self.store, year_month=datetime.date(2026, 4, 1),
            status='open',
        )
        self.client = Client()
        self.client.login(username='staff1', password='testpass123')

    def test_vacancy_stays_open_when_not_covered(self):
        vacancy = ShiftVacancy.objects.create(
            period=self.period, store=self.store,
            date=datetime.date(2026, 4, 10),
            start_hour=10, end_hour=14,
            staff_type='fortune_teller',
            required_count=2, assigned_count=0,
            status='open',
        )
        resp = self.client.post(
            f'/api/shift/vacancies/{vacancy.pk}/apply/',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        vacancy.refresh_from_db()
        # No assignments exist, so vacancy stays open
        self.assertEqual(vacancy.status, 'open')

    def test_vacancy_filled_when_covered(self):
        vacancy = ShiftVacancy.objects.create(
            period=self.period, store=self.store,
            date=datetime.date(2026, 4, 10),
            start_hour=10, end_hour=14,
            staff_type='fortune_teller',
            required_count=1, assigned_count=0,
            status='open',
        )
        # Create an existing assignment covering the vacancy
        ShiftAssignment.objects.create(
            period=self.period, staff=self.staff,
            date=datetime.date(2026, 4, 10),
            start_hour=10, end_hour=14,
        )
        resp = self.client.post(
            f'/api/shift/vacancies/{vacancy.pk}/apply/',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 201)
        vacancy.refresh_from_db()
        self.assertEqual(vacancy.status, 'filled')


# ===========================================================================
# 5. 撤回時 ChangeLog テスト
# ===========================================================================

class RevokeChangeLogTest(TestCase):
    def test_revoke_creates_change_logs(self):
        store = make_store()
        user = make_user('revoker')
        staff = make_staff(user, store, 'テスト', is_store_manager=True)
        period = ShiftPeriod.objects.create(
            store=store, year_month=datetime.date(2026, 4, 1),
            status='approved',
        )
        a1 = ShiftAssignment.objects.create(
            period=period, staff=staff,
            date=datetime.date(2026, 4, 5),
            start_hour=10, end_hour=18,
        )
        a2 = ShiftAssignment.objects.create(
            period=period, staff=staff,
            date=datetime.date(2026, 4, 6),
            start_hour=12, end_hour=20,
        )

        from booking.services.shift_scheduler import revoke_published_shifts
        revoke_published_shifts(period, reason='テスト撤回', revoked_by=staff)

        logs = ShiftChangeLog.objects.filter(
            assignment__period=period, change_type='revoked',
        )
        self.assertEqual(logs.count(), 2)
        log = logs.first()
        self.assertEqual(log.old_values['status'], 'approved')
        self.assertEqual(log.new_values['status'], 'scheduled')
        self.assertEqual(log.reason, 'テスト撤回')


# ===========================================================================
# 6. ChangeLog API テスト
# ===========================================================================

class ChangeLogAPITest(TestCase):
    def setUp(self):
        self.store = make_store()
        self.user = make_user('admin1', is_superuser=True)
        self.staff = make_staff(
            self.user, self.store, 'Admin',
            is_store_manager=True,
        )
        self.period = ShiftPeriod.objects.create(
            store=self.store, year_month=datetime.date(2026, 4, 1),
            status='approved',
        )
        self.assignment = ShiftAssignment.objects.create(
            period=self.period, staff=self.staff,
            date=datetime.date(2026, 4, 5),
            start_hour=10, end_hour=18,
        )
        self.log = ShiftChangeLog.objects.create(
            assignment=self.assignment,
            changed_by=self.staff,
            change_type='revised',
            old_values={'start_hour': 9},
            new_values={'start_hour': 10},
            reason='テスト変更',
        )
        self.client = Client()
        self.client.login(username='admin1', password='testpass123')

    def test_change_log_api_returns_logs(self):
        resp = self.client.get(
            '/api/shift/change-logs/',
        )
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertTrue(body['success'])
        results = body['data']['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['change_type'], 'revised')
        self.assertEqual(results[0]['reason'], 'テスト変更')

    def test_change_log_api_filter_by_period(self):
        resp = self.client.get(
            f'/api/shift/change-logs/?period_id={self.period.pk}',
        )
        body = json.loads(resp.content)
        self.assertEqual(body['data']['total'], 1)


# ===========================================================================
# 7. Store timezone テスト
# ===========================================================================

class StoreTimezoneTest(TestCase):
    def test_default_timezone(self):
        store = make_store()
        self.assertEqual(store.timezone, 'Asia/Tokyo')

    def test_custom_timezone(self):
        store = Store.objects.create(name='NYC Store', timezone='America/New_York')
        self.assertEqual(store.timezone, 'America/New_York')
