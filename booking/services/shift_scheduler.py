"""自動スケジューリング + Schedule同期 + 撤回・修正サービス"""
import datetime
import logging
from calendar import monthrange
from collections import defaultdict

from django.db import transaction
from django.db.models import Case, When, IntegerField
from django.utils import timezone

from booking.models import (
    ShiftAssignment,
    ShiftPublishHistory,
    ShiftChangeLog,
    ShiftStaffRequirement,
    ShiftStaffRequirementOverride,
    Schedule,
    StoreScheduleConfig,
    StoreClosedDate,
)
from booking.services.shift_coverage import (
    build_coverage_map,
    record_assignment,
    check_coverage_need,
    generate_vacancies,
)

logger = logging.getLogger(__name__)


def get_required_counts(store, target_date):
    """指定日の必要人数を取得（オーバーライド優先）

    Returns:
        dict: {staff_type: required_count}
    """
    overrides = ShiftStaffRequirementOverride.objects.filter(
        store=store, date=target_date,
    )
    if overrides.exists():
        return {o.staff_type: o.required_count for o in overrides}

    day_of_week = target_date.weekday()
    defaults = ShiftStaffRequirement.objects.filter(
        store=store, day_of_week=day_of_week,
    )
    return {d.staff_type: d.required_count for d in defaults}


def _get_store_config(store):
    """店舗のスケジュール設定を取得（なければデフォルト値）

    Returns:
        tuple: (open_h, close_h, duration, min_shift_hours)
    """
    config = getattr(store, 'schedule_config', None)
    if config is None:
        try:
            config = StoreScheduleConfig.objects.get(store=store)
        except StoreScheduleConfig.DoesNotExist:
            config = None
    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    duration = config.slot_duration if config else 60
    min_shift = getattr(config, 'min_shift_hours', 2) if config else 2
    return open_h, close_h, duration, min_shift


def _build_req_map(store, period):
    """期間内の全日付に対して必要人数マップを構築

    Returns:
        dict: {date: {staff_type: required_count}}
    """
    year = period.year_month.year
    month = period.year_month.month
    _, last_day = monthrange(year, month)

    req_map = {}
    for day in range(1, last_day + 1):
        d = datetime.date(year, month, day)
        counts = get_required_counts(store, d)
        if counts:
            req_map[d] = counts
    return req_map


def auto_schedule(period):
    """ShiftRequest → ShiftAssignment 自動生成（カバレッジベース）

    アルゴリズム:
    1. 既存アサイン全削除（再スケジューリング）
    2. リクエスト取得（unavailable除外、preferred→available順）
    3. 日付ごとの必要人数マップ構築
    4. カバレッジ追跡マップで各時間帯の充足状況を管理
    5. リクエストを1件ずつ処理:
       - 休業日/営業時間外/最低勤務時間未満 → skip
       - カバレッジ判定: 時間帯に空きがなければ skip
       - preferred は全時間帯充足でもアサイン（希望優先）
    6. 不足枠(ShiftVacancy)を自動生成
    """
    store = period.store
    open_h, close_h, duration, min_shift = _get_store_config(store)

    closed_dates = set(
        StoreClosedDate.objects.filter(store=store).values_list('date', flat=True)
    )

    req_map = _build_req_map(store, period)
    coverage_map = build_coverage_map()

    with transaction.atomic():
        period.assignments.all().delete()

        assigned_slots = defaultdict(set)

        preference_order = Case(
            When(preference='preferred', then=0),
            When(preference='available', then=1),
            default=2,
            output_field=IntegerField(),
        )
        requests = period.requests.exclude(
            preference='unavailable'
        ).select_related(
            'staff',
        ).annotate(
            pref_order=preference_order,
        ).order_by(
            'pref_order',
            'date',
            'start_hour',
        )

        created_count = 0
        for req in requests:
            # 休業日チェック
            if req.date in closed_dates:
                logger.info("Skipping request %s: store closed on %s", req, req.date)
                continue

            # 営業時間クリップ（はみ出し部分を営業時間内に切り詰め）
            eff_start = max(req.start_hour, open_h)
            eff_end = min(req.end_hour, close_h)
            if eff_start >= eff_end:
                logger.info(
                    "Skipping request %s: entirely outside business hours (%d-%d)",
                    req, open_h, close_h,
                )
                continue

            # 最低連続勤務時間チェック（クリップ後の実効時間で判定）
            shift_hours = eff_end - eff_start
            if shift_hours < min_shift:
                logger.info(
                    "Skipping request %s: clipped duration %dh < min %dh",
                    req, shift_hours, min_shift,
                )
                continue

            # 重複チェック
            slot_key = (req.date, eff_start)
            if req.staff_id in assigned_slots[slot_key]:
                continue

            # カバレッジ判定
            staff_type = req.staff.staff_type
            has_need = check_coverage_need(
                coverage_map, req_map, req.date, staff_type,
                eff_start, eff_end,
            )

            if not has_need and req.preference != 'preferred':
                logger.info(
                    "Skipping request %s: all hours fully covered",
                    req,
                )
                continue

            ShiftAssignment.objects.create(
                period=period,
                staff=req.staff,
                date=req.date,
                start_hour=eff_start,
                end_hour=eff_end,
                start_time=req.start_time or datetime.time(eff_start, 0),
                end_time=req.end_time or datetime.time(eff_end, 0),
            )
            assigned_slots[slot_key].add(req.staff_id)
            record_assignment(
                coverage_map, req.date, staff_type,
                eff_start, eff_end, req.staff_id,
            )
            created_count += 1

        # 不足枠の自動生成
        vacancy_count = generate_vacancies(
            period, store, req_map, coverage_map, open_h, close_h,
        )

        period.status = 'scheduled'
        period.save(update_fields=['status'])

    logger.info(
        "auto_schedule: period=%s, created %d assignments, %d vacancies",
        period, created_count, vacancy_count,
    )
    return created_count


def sync_assignments_to_schedule(period):
    """ShiftAssignment → Schedule レコード作成

    slot_duration に応じて分割（例: 2時間シフト → 60分コマなら2つのSchedule）
    customer_name=None, price=0 (空きコマ) として Schedule に同期
    """
    store = period.store
    _, _, duration, _ = _get_store_config(store)

    synced_count = 0
    assignments = period.assignments.filter(is_synced=False).select_related('staff')

    for assignment in assignments:
        # シフト時間を分単位に変換
        start_minutes = assignment.start_hour * 60
        end_minutes = assignment.end_hour * 60

        current = start_minutes
        while current + duration <= end_minutes:
            start_dt = datetime.datetime.combine(
                assignment.date,
                datetime.time(hour=current // 60, minute=current % 60),
            )
            end_dt = start_dt + datetime.timedelta(minutes=duration)

            # タイムゾーン対応
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)
            if timezone.is_naive(end_dt):
                end_dt = timezone.make_aware(end_dt)

            # 重複チェック: 既に同じスタッフ・同じ時間のScheduleがないか
            exists = Schedule.objects.filter(
                staff=assignment.staff,
                start=start_dt,
                is_cancelled=False,
            ).exists()

            if not exists:
                Schedule.objects.create(
                    staff=assignment.staff,
                    start=start_dt,
                    end=end_dt,
                    customer_name=None,
                    price=0,
                    is_temporary=False,
                    memo='シフトから自動作成',
                )
                synced_count += 1

            current += duration

        assignment.is_synced = True
        assignment.save(update_fields=['is_synced'])

    period.status = 'approved'
    period.save(update_fields=['status'])

    logger.info("sync_assignments_to_schedule: period=%s, synced %d schedules", period, synced_count)
    return synced_count


def revoke_published_shifts(period, reason, revoked_by=None):
    """公開済みシフトを撤回して scheduled に戻す

    1. period.status = 'scheduled' に戻す
    2. 期間に紐づく Schedule（memo='シフトから自動作成'）を is_cancelled=True に
    3. 全 ShiftAssignment の is_synced = False にリセット
    4. ShiftPublishHistory に action='revoke' エントリ作成
    """
    if period.status != 'approved':
        raise ValueError(f"撤回は approved 状態でのみ可能です (現在: {period.status})")

    with transaction.atomic():
        # Schedule レコードをキャンセル
        assignments = period.assignments.select_related('staff').all()
        staff_ids = set(a.staff_id for a in assignments)
        dates = set(a.date for a in assignments)

        if staff_ids and dates:
            min_date = min(dates)
            max_date = max(dates)
            cancelled_count = Schedule.objects.filter(
                staff_id__in=staff_ids,
                start__date__gte=min_date,
                start__date__lte=max_date,
                memo='シフトから自動作成',
                is_cancelled=False,
            ).update(is_cancelled=True)
        else:
            cancelled_count = 0

        # Assignment の同期フラグリセット
        period.assignments.update(is_synced=False)

        # ステータスを scheduled に戻す
        period.status = 'scheduled'
        period.save(update_fields=['status'])

        # 撤回履歴を記録
        ShiftPublishHistory.objects.create(
            period=period,
            published_by=revoked_by,
            assignment_count=period.assignments.count(),
            action='revoke',
            reason=reason,
        )

    logger.info(
        "revoke_published_shifts: period=%s, cancelled %d schedules, reason=%s",
        period, cancelled_count, reason,
    )
    return cancelled_count


def revert_scheduled(period, reason='', reverted_by=None):
    """スケジュール済み(scheduled)を open に戻す

    1. 全 ShiftAssignment を削除
    2. period.status = 'open' に戻す
    3. ShiftPublishHistory に action='revert' エントリ作成
    """
    if period.status != 'scheduled':
        raise ValueError(
            f"取消は scheduled 状態でのみ可能です (現在: {period.status})",
        )

    with transaction.atomic():
        deleted_count = period.assignments.count()
        period.assignments.all().delete()

        period.status = 'open'
        period.save(update_fields=['status'])

        ShiftPublishHistory.objects.create(
            period=period,
            published_by=reverted_by,
            assignment_count=deleted_count,
            action='revoke',
            reason=reason or 'スケジュール取消',
        )

    logger.info(
        "revert_scheduled: period=%s, deleted %d assignments, reason=%s",
        period, deleted_count, reason,
    )
    return deleted_count


def reopen_for_recruitment(period, reason='', reopened_by=None):
    """スケジュール済み(scheduled)を再募集(open)に戻す（既存アサインメント保持）

    1. period.status = 'open' に戻す（アサインメントは削除しない）
    2. ShiftPublishHistory に action='reopen' エントリ作成
    スタッフが追加希望を提出でき、再度自動配置を実行可能。
    """
    if period.status != 'scheduled':
        raise ValueError(
            f"再募集は scheduled 状態でのみ可能です (現在: {period.status})",
        )

    with transaction.atomic():
        assignment_count = period.assignments.count()

        period.status = 'open'
        period.save(update_fields=['status'])

        ShiftPublishHistory.objects.create(
            period=period,
            published_by=reopened_by,
            assignment_count=assignment_count,
            action='reopen',
            reason=reason or '再募集',
        )

    logger.info(
        "reopen_for_recruitment: period=%s, kept %d assignments, reason=%s",
        period, assignment_count, reason,
    )
    return assignment_count


def revise_assignment(assignment, new_data, revised_by=None, reason=''):
    """公開済みシフトの個別修正

    1. 変更前の値を snapshot
    2. assignment を更新
    3. ShiftChangeLog に記録
    4. 対応する Schedule レコードを更新（is_synced 済みの場合）
    """
    # 変更前の値をスナップショット
    tracked_fields = ['start_hour', 'end_hour', 'start_time', 'end_time', 'color', 'note']
    old_values = {}
    for field in tracked_fields:
        val = getattr(assignment, field)
        if hasattr(val, 'isoformat'):
            old_values[field] = val.isoformat()
        elif val is not None:
            old_values[field] = val

    with transaction.atomic():
        # assignment を更新
        new_values = {}
        for field in tracked_fields:
            if field in new_data:
                new_val = new_data[field]
                setattr(assignment, field, new_val)
                if hasattr(new_val, 'isoformat'):
                    new_values[field] = new_val.isoformat()
                elif new_val is not None:
                    new_values[field] = new_val

        assignment.save()

        # 変更ログ作成
        change_log = ShiftChangeLog.objects.create(
            assignment=assignment,
            changed_by=revised_by,
            change_type='revised',
            old_values=old_values,
            new_values=new_values,
            reason=reason,
        )

        # is_synced 済みの場合、対応 Schedule を更新
        if assignment.is_synced:
            _update_synced_schedules(assignment, old_values)

    logger.info("revise_assignment: assignment=%s, change_log=%s", assignment, change_log.pk)
    return change_log


def _update_synced_schedules(assignment, old_values):
    """同期済み Schedule を更新（旧時間帯のレコードをキャンセルし、新時間帯で再作成）"""
    store = assignment.period.store
    _, _, duration, _ = _get_store_config(store)

    old_start_h = old_values.get('start_hour', assignment.start_hour)
    old_end_h = old_values.get('end_hour', assignment.end_hour)

    # 旧時間帯の Schedule をキャンセル
    old_start_dt = datetime.datetime.combine(
        assignment.date,
        datetime.time(hour=int(old_start_h), minute=0),
    )
    old_end_dt = datetime.datetime.combine(
        assignment.date,
        datetime.time(hour=int(old_end_h), minute=0),
    )
    if timezone.is_naive(old_start_dt):
        old_start_dt = timezone.make_aware(old_start_dt)
    if timezone.is_naive(old_end_dt):
        old_end_dt = timezone.make_aware(old_end_dt)

    Schedule.objects.filter(
        staff=assignment.staff,
        start__gte=old_start_dt,
        start__lt=old_end_dt,
        memo='シフトから自動作成',
        is_cancelled=False,
    ).update(is_cancelled=True)

    # 新時間帯の Schedule を作成
    start_minutes = assignment.start_hour * 60
    end_minutes = assignment.end_hour * 60
    current = start_minutes
    while current + duration <= end_minutes:
        start_dt = datetime.datetime.combine(
            assignment.date,
            datetime.time(hour=current // 60, minute=current % 60),
        )
        end_dt = start_dt + datetime.timedelta(minutes=duration)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)

        Schedule.objects.create(
            staff=assignment.staff,
            start=start_dt,
            end=end_dt,
            customer_name=None,
            price=0,
            is_temporary=False,
            memo='シフトから自動作成',
        )
        current += duration
