"""当日分のデモデータを自動生成するコマンド。

Celeryタスクから30分毎に呼ばれ、現在時刻までの当日デモデータを生成する。
既存の当日デモデータがあれば差分だけ追加する。

Usage:
    python manage.py generate_live_demo_data
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import (
    Store, Staff, Product, Order, OrderItem,
    Schedule, VisitorCount, SiteSettings,
    WorkAttendance, AttendanceStamp,
    ShiftPeriod, ShiftAssignment,
)


class Command(BaseCommand):
    help = '当日分のデモデータを現在時刻まで自動生成（is_demo=True）'

    def handle(self, *args, **options):
        if not SiteSettings.load().demo_mode_enabled:
            self.stdout.write('デモモード無効 — スキップ')
            return

        store = Store.objects.first()
        if not store:
            self.stderr.write('Store が存在しません')
            return

        now = timezone.localtime(timezone.now())
        today = now.date()
        current_hour = now.hour

        self._generate_shifts(store, today, current_hour, now)
        self._generate_orders(store, today, current_hour, now)
        self._generate_schedules(store, today, current_hour, now)
        self._generate_visitor_counts(store, today, current_hour)
        self._generate_attendance(store, today, current_hour, now)
        self._generate_checkins(store, today, now)

        self.stdout.write(self.style.SUCCESS('当日デモデータ生成完了'))

    def _generate_shifts(self, store, today, current_hour, now):
        """当日のシフト割当デモデータ"""
        from datetime import time as dt_time

        # 既にデモシフトがあればスキップ
        existing = ShiftAssignment.objects.filter(
            date=today, is_demo=True, period__store=store,
        ).count()
        if existing > 0:
            return

        staffs = list(Staff.objects.filter(store=store))
        if not staffs:
            return

        # 当月のデモ用 ShiftPeriod を取得 or 作成
        month_start = today.replace(day=1)
        period, _ = ShiftPeriod.objects.get_or_create(
            store=store,
            year_month=month_start,
            is_demo=True,
            defaults={
                'status': 'approved',
            },
        )

        # シフトパターン: 早番(9-15), 遅番(14-21), 通し(9-18)
        shift_patterns = [
            (9, 15, '#10B981'),   # 早番 green
            (14, 21, '#6366F1'),  # 遅番 indigo
            (9, 18, '#3B82F6'),   # 通し blue
        ]

        created = 0
        for staff in staffs:
            if random.random() < 0.15:  # 15%は休み
                continue
            pattern = random.choice(shift_patterns)
            start_h, end_h, color = pattern
            ShiftAssignment.objects.create(
                period=period,
                staff=staff,
                date=today,
                start_hour=start_h,
                end_hour=end_h,
                start_time=dt_time(start_h, 0),
                end_time=dt_time(end_h, 0),
                store=store,
                color=color,
                note='デモシフト',
                is_demo=True,
            )
            created += 1

        if created:
            self.stdout.write(f'  Shift: {created}件生成')

    def _generate_orders(self, store, today, current_hour, now):
        """当日の注文デモデータ（営業時間: 10-22時）"""
        products = list(Product.objects.filter(store=store, is_active=True)[:20])
        if not products:
            return

        existing_hours = set(
            Order.objects.filter(
                store=store, is_demo=True,
                created_at__date=today,
            ).values_list('created_at__hour', flat=True).distinct()
        )

        created = 0
        for hour in range(10, min(current_hour + 1, 23)):
            if hour in existing_hours:
                continue
            num_orders = random.randint(1, 4)
            for _ in range(num_orders):
                order_time = now.replace(
                    hour=hour, minute=random.randint(0, 59), second=0,
                )
                order = Order.objects.create(
                    store=store,
                    status='CLOSED',
                    payment_status='paid',
                    channel=random.choice(['pos', 'table', 'reservation']),
                    is_demo=True,
                )
                Order.objects.filter(pk=order.pk).update(created_at=order_time)

                sample_prods = random.sample(products, min(random.randint(1, 4), len(products)))
                for prod in sample_prods:
                    qty = random.randint(1, 2)
                    OrderItem.objects.create(
                        order=order, product=prod,
                        qty=qty, unit_price=prod.price,
                        status='CLOSED',
                    )
                created += 1

        if created:
            self.stdout.write(f'  Order: {created}件生成')

    def _generate_schedules(self, store, today, current_hour, now):
        """当日の予約デモデータ"""
        staff_list = list(Staff.objects.filter(store=store, staff_type='fortune_teller'))
        if not staff_list:
            return

        existing = Schedule.objects.filter(
            start__date=today, is_demo=True,
        ).count()
        if existing >= 10:
            return

        created = 0
        for hour in range(10, min(current_hour + 2, 23)):
            if random.random() < 0.4:
                continue
            staff = random.choice(staff_list)
            start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
            end = start + timedelta(minutes=random.choice([30, 60]))
            Schedule.objects.create(
                staff=staff,
                start=start,
                end=end,
                customer_name=random.choice([
                    '田中 花子', '佐藤 太郎', '鈴木 一郎', '高橋 美咲',
                ]),
                is_temporary=False,
                is_cancelled=False,
                price=staff.price,
                memo='ライブデモデータ',
                is_demo=True,
            )
            created += 1

        if created:
            self.stdout.write(f'  Schedule: {created}件生成')

    def _generate_visitor_counts(self, store, today, current_hour):
        """当日の来客数デモデータ"""
        existing_hours = set(
            VisitorCount.objects.filter(
                store=store, date=today, is_demo=True,
            ).values_list('hour', flat=True)
        )

        created = 0
        for hour in range(9, min(current_hour + 1, 23)):
            if hour in existing_hours:
                continue
            base = random.randint(5, 30)
            if 12 <= hour <= 14 or 18 <= hour <= 20:
                base = int(base * 1.5)
            VisitorCount.objects.update_or_create(
                store=store, date=today, hour=hour,
                defaults={
                    'estimated_visitors': base,
                    'pir_count': base + random.randint(0, 10),
                    'order_count': max(1, base // 3),
                    'is_demo': True,
                },
            )
            created += 1

        if created:
            self.stdout.write(f'  VisitorCount: {created}件生成')

    def _generate_attendance(self, store, today, current_hour, now):
        """当日の出退勤デモデータ（AttendanceStamp + WorkAttendance）"""
        staffs = list(Staff.objects.filter(store=store))
        if not staffs:
            return

        # 既にデモ打刻があればスキップ
        existing = AttendanceStamp.objects.filter(
            staff__store=store,
            stamped_at__date=today,
            is_demo=True,
        ).count()
        if existing > 0:
            return

        created = 0
        for staff in staffs:
            # 各スタッフにランダムなシナリオを割り当て
            # 出勤開始は9〜11時
            clock_in_hour = random.randint(9, 11)
            if clock_in_hour > current_hour:
                continue  # まだ出勤前

            clock_in_minute = random.randint(0, 15)
            clock_in_time = now.replace(
                hour=clock_in_hour, minute=clock_in_minute,
                second=0, microsecond=0,
            )

            # 出勤打刻
            AttendanceStamp.objects.create(
                staff=staff,
                stamp_type='clock_in',
                totp_used='',
                is_demo=True,
            )
            # stamped_at は auto_now_add なので update で上書き
            AttendanceStamp.objects.filter(
                staff=staff, is_demo=True, stamp_type='clock_in',
                stamped_at__date=today,
            ).update(stamped_at=clock_in_time)

            # WorkAttendance レコード
            wa, _ = WorkAttendance.objects.update_or_create(
                staff=staff, date=today,
                defaults={
                    'clock_in': clock_in_time.time(),
                    'source': 'qr',
                    'is_demo': True,
                },
            )

            scenario = random.choice(['working', 'break', 'left'])

            # 退勤済シナリオ: 十分時間が経過している場合のみ
            if scenario == 'left' and current_hour >= clock_in_hour + 6:
                clock_out_hour = clock_in_hour + random.randint(6, 9)
                if clock_out_hour > current_hour:
                    clock_out_hour = current_hour - 1
                if clock_out_hour <= clock_in_hour:
                    scenario = 'working'
                else:
                    clock_out_time = now.replace(
                        hour=clock_out_hour, minute=random.randint(0, 30),
                        second=0, microsecond=0,
                    )
                    AttendanceStamp.objects.create(
                        staff=staff, stamp_type='clock_out',
                        totp_used='', is_demo=True,
                    )
                    AttendanceStamp.objects.filter(
                        staff=staff, is_demo=True, stamp_type='clock_out',
                        stamped_at__date=today,
                    ).update(stamped_at=clock_out_time)
                    wa.clock_out = clock_out_time.time()
                    wa.regular_minutes = (clock_out_hour - clock_in_hour) * 60
                    wa.save(update_fields=['clock_out', 'regular_minutes'])

            # 休憩中シナリオ
            if scenario == 'break' and current_hour >= clock_in_hour + 3:
                break_hour = clock_in_hour + random.randint(3, 4)
                if break_hour <= current_hour:
                    break_time = now.replace(
                        hour=break_hour, minute=random.randint(0, 15),
                        second=0, microsecond=0,
                    )
                    AttendanceStamp.objects.create(
                        staff=staff, stamp_type='break_start',
                        totp_used='', is_demo=True,
                    )
                    AttendanceStamp.objects.filter(
                        staff=staff, is_demo=True, stamp_type='break_start',
                        stamped_at__date=today,
                    ).update(stamped_at=break_time)

            created += 1

        if created:
            self.stdout.write(f'  Attendance: {created}件生成')

    def _generate_checkins(self, store, today, now):
        """当日の予約にチェックイン済みフラグを付与"""
        past_schedules = Schedule.objects.filter(
            start__date=today,
            start__lte=now,
            is_demo=True,
            is_checked_in=False,
            is_cancelled=False,
        )

        updated = 0
        for sched in past_schedules:
            if random.random() < 0.7:  # 70%の確率でチェックイン済み
                sched.is_checked_in = True
                sched.checked_in_at = sched.start + timedelta(minutes=random.randint(-5, 10))
                sched.save(update_fields=['is_checked_in', 'checked_in_at'])
                updated += 1

        if updated:
            self.stdout.write(f'  Checkin: {updated}件更新')
