"""カバレッジ計算ヘルパー — auto_schedule のサブモジュール"""
import logging
from collections import defaultdict

from django.db import transaction

from booking.models import ShiftVacancy

logger = logging.getLogger(__name__)


def build_coverage_map():
    """空のカバレッジ追跡マップを生成

    Returns:
        defaultdict: {date: {staff_type: {hour: set(staff_ids)}}}
    """
    return defaultdict(lambda: defaultdict(lambda: defaultdict(set)))


def record_assignment(coverage_map, date, staff_type, start_h, end_h, staff_id):
    """アサインをカバレッジマップに記録"""
    for h in range(start_h, end_h):
        coverage_map[date][staff_type][h].add(staff_id)


def check_coverage_need(coverage_map, req_map, date, staff_type, start_h, end_h):
    """リクエストの時間範囲内で、定員未達の時間があるか判定

    Args:
        coverage_map: カバレッジ追跡マップ
        req_map: {date: {staff_type: required_count}}
        date: 対象日
        staff_type: スタッフ種別
        start_h: リクエスト開始時間
        end_h: リクエスト終了時間

    Returns:
        bool: 空きがあればTrue（このリクエストが必要）
    """
    required = req_map.get(date, {}).get(staff_type, 0)
    if required == 0:
        return True  # 定員未設定 → 制限なし

    for h in range(start_h, end_h):
        assigned = len(coverage_map[date][staff_type].get(h, set()))
        if assigned < required:
            return True
    return False


def count_coverage_hours(coverage_map, req_map, date, staff_type, start_h, end_h):
    """リクエストの時間範囲内で、定員未達の時間数を返す"""
    required = req_map.get(date, {}).get(staff_type, 0)
    if required == 0:
        return end_h - start_h  # 定員未設定 → 全時間が必要

    needed_hours = 0
    for h in range(start_h, end_h):
        assigned = len(coverage_map[date][staff_type].get(h, set()))
        if assigned < required:
            needed_hours += 1
    return needed_hours


@transaction.atomic
def generate_vacancies(period, store, req_map, coverage_map, open_h, close_h):
    """カバレッジ不足の時間帯を ShiftVacancy として保存（連続時間をマージ）

    Args:
        period: ShiftPeriod
        store: Store
        req_map: {date: {staff_type: required_count}}
        coverage_map: カバレッジ追跡マップ
        open_h: 営業開始時間
        close_h: 営業終了時間

    Returns:
        int: 生成した ShiftVacancy 数
    """
    period.vacancies.all().delete()
    created_count = 0

    for date in sorted(req_map.keys()):
        for staff_type, required in req_map[date].items():
            if required <= 0:
                continue

            shortage_start = None
            min_assigned_in_run = None

            for h in range(open_h, close_h):
                assigned = len(coverage_map[date][staff_type].get(h, set()))
                if assigned < required:
                    if shortage_start is None:
                        shortage_start = h
                        min_assigned_in_run = assigned
                    else:
                        min_assigned_in_run = min(min_assigned_in_run, assigned)
                else:
                    if shortage_start is not None:
                        ShiftVacancy.objects.create(
                            period=period,
                            store=store,
                            date=date,
                            start_hour=shortage_start,
                            end_hour=h,
                            staff_type=staff_type,
                            required_count=required,
                            assigned_count=min_assigned_in_run,
                            status='open',
                        )
                        created_count += 1
                        shortage_start = None
                        min_assigned_in_run = None

            # 末尾処理
            if shortage_start is not None:
                ShiftVacancy.objects.create(
                    period=period,
                    store=store,
                    date=date,
                    start_hour=shortage_start,
                    end_hour=close_h,
                    staff_type=staff_type,
                    required_count=required,
                    assigned_count=min_assigned_in_run,
                    status='open',
                )
                created_count += 1

    logger.info(
        "generate_vacancies: period=%s, created %d vacancy records",
        period, created_count,
    )
    return created_count
