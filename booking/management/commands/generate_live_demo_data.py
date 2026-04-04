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

        now = timezone.now()
        today = now.date()
        current_hour = now.hour

        self._generate_orders(store, today, current_hour, now)
        self._generate_schedules(store, today, current_hour, now)
        self._generate_visitor_counts(store, today, current_hour)

        self.stdout.write(self.style.SUCCESS('当日デモデータ生成完了'))

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
