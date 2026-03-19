"""Staff shift submission views: StaffShiftCalendarView,
StaffShiftSubmitView, StaffShiftSubmitByMonthView,
StaffShiftBulkRequestAPIView, StaffShiftCopyWeekAPIView."""
import calendar
import datetime
import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import generic, View

from booking.models import (
    Staff, ShiftPeriod, ShiftRequest, ShiftTemplate,
    ShiftVacancy, StoreClosedDate, StoreScheduleConfig,
)
from booking.validators import validate_business_hours, validate_min_shift, validate_closed_date
from booking.api_response import success_response, error_response

logger = logging.getLogger(__name__)


def _get_hour_range(store):
    """店舗の営業時間範囲を返す（views.get_hour_range の軽量版）"""
    try:
        config = store.schedule_config
    except StoreScheduleConfig.DoesNotExist:
        config = None
    open_h = config.open_hour if config else 9
    close_h = config.close_hour if config else 21
    return open_h, close_h


def _get_or_create_shift_period(store, year, month, staff=None):
    """月指定で ShiftPeriod を自動取得/作成する"""
    ym = datetime.date(year, month, 1)
    period, _ = ShiftPeriod.objects.get_or_create(
        store=store, year_month=ym,
        defaults={'status': 'open', 'created_by': staff},
    )
    return period


class StaffShiftCalendarView(LoginRequiredMixin, generic.TemplateView):
    """占い師が自分のシフトカレンダーを表示（当月~翌2ヶ月を常時表示）"""
    template_name = 'booking/staff_shift_calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = get_object_or_404(Staff, user=self.request.user)
        today = datetime.date.today()

        # 当月~翌2ヶ月の月リストを生成
        months = []
        for offset in range(3):
            y = today.year + (today.month + offset - 1) // 12
            m = (today.month + offset - 1) % 12 + 1
            ym = datetime.date(y, m, 1)
            period = ShiftPeriod.objects.filter(
                store=staff.store, year_month=ym,
            ).first()
            request_count = ShiftRequest.objects.filter(
                staff=staff, period=period,
            ).count() if period else 0
            months.append({
                'year': y,
                'month': m,
                'year_month': ym,
                'period': period,
                'request_count': request_count,
            })

        # 自分のシフト希望（最近3ヶ月分）
        three_months_ago = datetime.date(months[0]['year'], months[0]['month'], 1)
        my_requests = ShiftRequest.objects.filter(
            staff=staff,
            date__gte=three_months_ago,
        ).select_related('period').order_by('date', 'start_hour')

        # 再募集枠（スタッフ種別に合わせて表示）
        vacancies = ShiftVacancy.objects.filter(
            store=staff.store,
            status='open',
            date__gte=today,
            staff_type=staff.staff_type,
        ).order_by('date', 'start_hour')[:20]

        # 受付中のシフト期間（テスト互換）
        open_periods = ShiftPeriod.objects.filter(
            store=staff.store, status='open',
        ).order_by('-year_month')

        context['staff'] = staff
        context['today'] = today
        context['months'] = months
        context['my_requests'] = my_requests
        context['vacancies'] = vacancies
        context['open_periods'] = open_periods
        return context


class StaffShiftSubmitView(LoginRequiredMixin, View):
    """占い師がシフト希望を登録/変更"""

    def get(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)
        open_h, close_h = _get_hour_range(staff.store)

        existing = ShiftRequest.objects.filter(
            period=period, staff=staff,
        ).order_by('date', 'start_hour')

        # テンプレート一覧
        templates = ShiftTemplate.objects.filter(
            store=staff.store, is_active=True,
        ).order_by('sort_order', 'name')

        # カレンダー用: 対象月の日付リスト
        year_month = period.year_month
        _, days_in_month = calendar.monthrange(year_month.year, year_month.month)
        month_dates = [
            datetime.date(year_month.year, year_month.month, d)
            for d in range(1, days_in_month + 1)
        ]

        # 既存リクエストを日付→リスト辞書に変換（JSON用）
        existing_map = {}
        for req in existing:
            key = req.date.isoformat()
            if key not in existing_map:
                existing_map[key] = []
            existing_map[key].append({
                'start_hour': req.start_hour,
                'end_hour': req.end_hour,
                'preference': req.preference,
                'note': req.note,
            })

        # テンプレートJSON用
        templates_json = [
            {
                'id': t.id,
                'name': t.name,
                'start_hour': t.start_time.hour,
                'end_hour': t.end_time.hour,
                'color': t.color,
            }
            for t in templates
        ]

        # 休業日リスト（JSON用）
        closed_dates = list(
            StoreClosedDate.objects.filter(
                store=staff.store,
                date__year=year_month.year,
                date__month=year_month.month,
            ).values_list('date', flat=True)
        )
        closed_dates_json = json.dumps([d.isoformat() for d in closed_dates])

        # 最低シフト時間
        try:
            config = StoreScheduleConfig.objects.get(store=staff.store)
            min_shift_hours = config.min_shift_hours
        except StoreScheduleConfig.DoesNotExist:
            min_shift_hours = 2

        return render(request, 'booking/staff_shift_submit.html', {
            'staff': staff,
            'period': period,
            'existing': existing,
            'open_hour': open_h,
            'close_hour': close_h,
            'templates': templates,
            'templates_json': json.dumps(templates_json),
            'existing_map_json': json.dumps(existing_map),
            'closed_dates_json': closed_dates_json,
            'month_dates': month_dates,
            'year_month': year_month,
            'min_shift_hours': min_shift_hours,
        })

    def post(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)

        if period.status == 'closed':
            messages.error(request, 'この期間は締め切られています。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        open_h, close_h = _get_hour_range(staff.store)

        date_str = request.POST.get('date')
        start_hour = request.POST.get('start_hour')
        end_hour = request.POST.get('end_hour')
        preference = request.POST.get('preference', 'available')
        note = request.POST.get('note', '')

        if not all([date_str, start_hour, end_hour]):
            messages.error(request, '日付と時間を入力してください。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        try:
            date = datetime.date.fromisoformat(date_str)
            start_h = int(start_hour)
            end_h = int(end_hour)
        except (ValueError, TypeError):
            messages.error(request, '入力値が不正です。')
            return redirect('booking:staff_shift_submit', period_id=period_id)

        # 休業日チェック
        closed_err = validate_closed_date(staff.store, date)
        if closed_err:
            messages.error(request, closed_err)
            return redirect('booking:staff_shift_submit', period_id=period_id)

        # 営業時間バリデーション
        bh_err = validate_business_hours(start_h, end_h, open_h, close_h)
        if bh_err:
            messages.error(request, bh_err)
            return redirect('booking:staff_shift_submit', period_id=period_id)

        # 最低連続勤務時間チェック（unavailable以外）
        _, min_shift_err = validate_min_shift(staff.store, start_h, end_h, preference)
        if min_shift_err:
            messages.error(request, min_shift_err)
            return redirect('booking:staff_shift_submit', period_id=period_id)

        ShiftRequest.objects.update_or_create(
            period=period,
            staff=staff,
            date=date,
            start_hour=start_h,
            defaults={
                'end_hour': end_h,
                'preference': preference,
                'note': note,
            },
        )

        messages.success(request, 'シフト希望を登録しました。')
        return redirect('booking:staff_shift_submit', period_id=period_id)


class StaffShiftSubmitByMonthView(LoginRequiredMixin, View):
    """月指定でアクセス -> Period自動作成 -> 既存SubmitViewへ委譲"""

    def dispatch(self, request, year, month, *args, **kwargs):
        staff = get_object_or_404(Staff, user=request.user)
        period = _get_or_create_shift_period(staff.store, year, month, staff=staff)
        return redirect('booking:staff_shift_submit', period_id=period.pk)


class StaffShiftBulkRequestAPIView(LoginRequiredMixin, View):
    """スタッフがカレンダーUIからシフト希望を一括登録するAPI"""

    def post(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)

        if period.status == 'closed':
            return error_response('この期間は締め切られています。')

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        entries = data.get('entries', [])
        if not entries:
            return error_response('entries が空です。')

        open_h, close_h = _get_hour_range(staff.store)
        # 休業日を一括取得
        entry_dates = set()
        for entry in entries:
            try:
                entry_dates.add(datetime.date.fromisoformat(entry['date']))
            except (KeyError, ValueError, TypeError):
                pass
        closed_dates = set(
            StoreClosedDate.objects.filter(
                store=staff.store, date__in=entry_dates,
            ).values_list('date', flat=True)
        )

        created = 0
        updated = 0
        errors = []

        with transaction.atomic():
            for entry in entries:
                try:
                    date = datetime.date.fromisoformat(entry['date'])
                    start_h = int(entry['start_hour'])
                    end_h = int(entry['end_hour'])
                    preference = entry.get('preference', 'available')
                    note = entry.get('note', '')
                except (KeyError, ValueError, TypeError) as e:
                    errors.append(f"Invalid entry: {entry} ({e})")
                    continue

                if date in closed_dates:
                    errors.append(f"{date}: 休業日のためシフトを入れられません")
                    continue

                bh_err = validate_business_hours(start_h, end_h, open_h, close_h)
                if bh_err:
                    errors.append(f"{date}: 営業時間外 ({start_h}-{end_h})")
                    continue

                _, was_created = ShiftRequest.objects.update_or_create(
                    period=period,
                    staff=staff,
                    date=date,
                    start_hour=start_h,
                    defaults={
                        'end_hour': end_h,
                        'preference': preference,
                        'note': note,
                    },
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        return success_response({
            'created': created,
            'updated': updated,
            'errors': errors,
        })

    def delete(self, request, period_id):
        """指定日のシフト希望を削除"""
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        dates = data.get('dates', [])
        if not dates:
            return error_response('dates が空です。')

        parsed_dates = []
        for d in dates:
            try:
                parsed_dates.append(datetime.date.fromisoformat(d))
            except (ValueError, TypeError):
                pass

        deleted_count, _ = ShiftRequest.objects.filter(
            period=period, staff=staff, date__in=parsed_dates,
        ).delete()

        return success_response({'deleted': deleted_count})


class StaffShiftCopyWeekAPIView(LoginRequiredMixin, View):
    """前週のシフト希望を翌週にコピーするAPI"""

    def post(self, request, period_id):
        staff = get_object_or_404(Staff, user=request.user)
        period = get_object_or_404(ShiftPeriod, pk=period_id, store=staff.store)

        if period.status == 'closed':
            return error_response('この期間は締め切られています。')

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return error_response('Invalid JSON')

        source_start = data.get('source_week_start')  # e.g. "2026-03-09"
        target_start = data.get('target_week_start')   # e.g. "2026-03-16"

        if not source_start or not target_start:
            return error_response('source_week_start と target_week_start が必要です。')

        try:
            src_start = datetime.date.fromisoformat(source_start)
            tgt_start = datetime.date.fromisoformat(target_start)
        except ValueError:
            return error_response('日付形式が不正です。')

        src_end = src_start + timedelta(days=6)
        tgt_end = tgt_start + timedelta(days=6)
        source_requests = ShiftRequest.objects.filter(
            period=period, staff=staff,
            date__gte=src_start, date__lte=src_end,
        )

        # ターゲット週の休業日を取得
        target_closed = set(
            StoreClosedDate.objects.filter(
                store=staff.store,
                date__gte=tgt_start,
                date__lte=tgt_end,
            ).values_list('date', flat=True)
        )

        created = 0
        skipped = 0
        for req in source_requests:
            day_offset = (req.date - src_start).days
            new_date = tgt_start + timedelta(days=day_offset)

            if new_date in target_closed:
                skipped += 1
                continue

            _, was_created = ShiftRequest.objects.update_or_create(
                period=period,
                staff=staff,
                date=new_date,
                start_hour=req.start_hour,
                defaults={
                    'end_hour': req.end_hour,
                    'preference': req.preference,
                    'note': req.note,
                },
            )
            if was_created:
                created += 1

        return success_response({'created': created, 'skipped': skipped})
