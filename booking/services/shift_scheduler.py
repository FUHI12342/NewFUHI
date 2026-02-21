"""自動スケジューリング + Schedule同期サービス"""
import datetime
import logging

from django.utils import timezone

from booking.models import (
    ShiftPeriod,
    ShiftRequest,
    ShiftAssignment,
    Schedule,
    StoreScheduleConfig,
)

logger = logging.getLogger(__name__)


def _get_store_config(store):
    """店舗のスケジュール設定を取得（なければデフォルト値）"""
    config = getattr(store, 'schedule_config', None)
    if config is None:
        try:
            config = StoreScheduleConfig.objects.get(store=store)
        except StoreScheduleConfig.DoesNotExist:
            config = None
    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    duration = config.slot_duration if config else 60
    return open_h, close_h, duration


def auto_schedule(period):
    """ShiftRequest → ShiftAssignment 自動生成

    - preference='preferred' を最優先で割り当て
    - preference='available' で埋める
    - preference='unavailable' は除外
    - 営業時間外はブロック
    - 同一店舗・同一時間帯の重複チェック（占い師間）
    """
    store = period.store
    open_h, close_h, duration = _get_store_config(store)

    # 既存のアサインメントをクリア（再スケジューリング対応）
    period.assignments.all().delete()

    # 割り当て済みスロットの追跡: (date, start_hour) → staff_id のセット
    assigned_slots = {}

    requests = period.requests.exclude(
        preference='unavailable'
    ).order_by(
        # preferred を先に処理
        '-preference',  # 'preferred' > 'available' (alphabetically reversed)
        'date',
        'start_hour',
    )

    created_count = 0
    for req in requests:
        # 営業時間外チェック
        if req.start_hour < open_h or req.end_hour > close_h:
            logger.info(
                "Skipping request %s: outside business hours (%d-%d)",
                req, open_h, close_h,
            )
            continue

        # 重複チェック: 同一日・同一時間帯に既にアサインされていないか
        slot_key = (req.date, req.start_hour)
        if slot_key not in assigned_slots:
            assigned_slots[slot_key] = set()

        if req.staff_id in assigned_slots[slot_key]:
            continue  # 既にこのスタッフはこのスロットにアサイン済み

        ShiftAssignment.objects.create(
            period=period,
            staff=req.staff,
            date=req.date,
            start_hour=req.start_hour,
            end_hour=req.end_hour,
        )
        assigned_slots[slot_key].add(req.staff_id)
        created_count += 1

    period.status = 'scheduled'
    period.save(update_fields=['status'])

    logger.info("auto_schedule: period=%s, created %d assignments", period, created_count)
    return created_count


def sync_assignments_to_schedule(period):
    """ShiftAssignment → Schedule レコード作成

    slot_duration に応じて分割（例: 2時間シフト → 60分コマなら2つのSchedule）
    customer_name=None, price=0 (空きコマ) として Schedule に同期
    """
    store = period.store
    _, _, duration = _get_store_config(store)

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
