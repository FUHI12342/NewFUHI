"""
売上データ1年分拡充コマンド

既存の90日分データに加え、91日前〜365日前の注文を追加生成。
EC注文(全期間) + 店内注文(91-365日前分)を生成する。

Usage:
    python manage.py extend_order_data
    python manage.py extend_order_data --reset   # 追加分だけ削除して再生成
    python manage.py extend_order_data --ec-only  # EC注文のみ生成
"""
import hashlib
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import F as models_F, Min
from django.utils import timezone

from booking.models import (
    Order, OrderItem, POSTransaction,
    Product, Store, Staff, TableSeat, PaymentMethod,
    Schedule, VisitorCount, CustomerFeedback,
)

# 注文識別用メモ
EXTEND_MEMO = 'extend_order_data'

# 季節係数: 1月=0.70 … 12月=1.20
MONTHLY_COEFF = [0.70, 0.75, 0.85, 0.95, 1.00, 0.80, 0.90, 0.85, 0.90, 1.05, 1.10, 1.20]

# 曜日係数: 月=0.60 … 日=1.00
WEEKDAY_COEFF = [0.65, 0.65, 0.70, 0.80, 1.20, 1.40, 1.00]

# EC曜日係数 (平日が多い)
EC_WEEKDAY_COEFF = [1.00, 1.00, 0.95, 0.90, 0.85, 0.75, 0.80]

# 顧客名プール (コホート/RFM分析用)
CUSTOMER_NAMES = [
    '田中 花子', '佐藤 太郎', '鈴木 一郎', '高橋 美咲',
    '渡辺 健', '伊藤 さくら', '山本 翔太', '中村 美月',
    '小林 優子', '加藤 大輝', '吉田 あかり', '山田 蓮',
    '松本 結衣', '井上 陸', '木村 凛', '林 悠人',
    '斎藤 楓', '清水 蒼', '山口 芽依', '池田 颯太',
    '橋本 琴音', '阿部 湊', '石川 千尋', '前田 樹',
    '藤田 茉白', '岡田 瑛太', '後藤 七海', '長谷川 暖',
    '村上 日葵', '近藤 奏', '坂本 真央', '遠藤 大和',
    '青木 柚月', '藤井 雫', '西村 陽向', '福田 凪',
    '太田 碧', '三浦 朝陽', '岡本 栞', '松田 律',
]


def _customer_hash(name):
    """顧客名からLINEハッシュ風の固定ハッシュを生成"""
    return hashlib.sha256(f'demo_{name}'.encode()).hexdigest()[:32]


class Command(BaseCommand):
    help = '売上データを1年分に拡充（EC注文 + 店内注文追加）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='追加データを削除してから再生成',
        )
        parser.add_argument(
            '--ec-only', action='store_true',
            help='EC注文のみ生成（店内追加はスキップ）',
        )

    def handle(self, *args, **options):
        self.store = Store.objects.first()
        if not self.store:
            self.stderr.write('Store が存在しません。')
            return

        if options['reset']:
            self._reset()

        # EC商品がなければ先にseed_ec_goodsを実行
        ec_products = list(
            Product.objects.filter(
                store=self.store, is_ec_visible=True, is_active=True,
            )
        )
        if not ec_products:
            self.stdout.write(self.style.WARNING(
                'EC商品がありません。先に python manage.py seed_ec_goods を実行してください。'))
            return

        instore_products = list(
            Product.objects.filter(
                store=self.store, is_active=True,
            ).exclude(sku__startswith='EC-')
        )

        tables = list(TableSeat.objects.filter(store=self.store, is_active=True))
        staff_list = list(Staff.objects.filter(store=self.store))
        payment_methods = list(PaymentMethod.objects.filter(store=self.store, is_enabled=True))

        now = timezone.now()

        # 既存データの最古の日付を確認
        oldest = Order.objects.filter(store=self.store).aggregate(
            oldest=Min('created_at'))['oldest']
        if oldest:
            existing_days = (now - oldest).days
            self.stdout.write(f'既存データ: {existing_days}日分')
        else:
            existing_days = 0

        # 顧客プール作成 (固定ハッシュ)
        customer_pool = [
            {'name': name, 'hash': _customer_hash(name)}
            for name in CUSTOMER_NAMES
        ]
        # リピーター確率のために顧客に重み付け
        # 上位10名は常連 (高頻度), 中間15名は普通, 残り15名は低頻度
        regulars = customer_pool[:10]
        normals = customer_pool[10:25]
        occasionals = customer_pool[25:]

        receipt_counter = POSTransaction.objects.count() + 2000

        # ── EC注文生成 (全365日分) ──
        ec_created = 0
        for days_ago in range(365, 0, -1):
            order_date = now - timedelta(days=days_ago)
            month = order_date.month - 1
            weekday = order_date.weekday()

            base_orders = 2
            coeff = MONTHLY_COEFF[month] * EC_WEEKDAY_COEFF[weekday]
            daily_ec = max(1, int(base_orders * coeff + random.uniform(-0.5, 1.5)))

            for _ in range(daily_ec):
                hour = random.choice([9, 10, 11, 12, 13, 14, 20, 21, 22])
                order_time = order_date.replace(
                    hour=hour, minute=random.randint(0, 59), second=0,
                )

                # 顧客選択 (リピーター偏重)
                r = random.random()
                if r < 0.35:
                    customer = random.choice(regulars)
                elif r < 0.70:
                    customer = random.choice(normals)
                else:
                    customer = random.choice(occasionals)

                order = Order.objects.create(
                    store=self.store,
                    channel='ec',
                    status='CLOSED',
                    payment_status='paid',
                    customer_name=customer['name'],
                    customer_line_user_hash=customer['hash'],
                    customer_email=f'{customer["hash"][:8]}@example.com',
                    shipping_status='delivered',
                    shipping_fee=500 if random.random() > 0.3 else 0,
                    discount_amount=0,
                )
                Order.objects.filter(pk=order.pk).update(created_at=order_time)

                num_items = random.randint(1, 3)
                total = 0
                for prod in random.sample(ec_products, min(num_items, len(ec_products))):
                    qty = 1
                    OrderItem.objects.create(
                        order=order, product=prod,
                        qty=qty, unit_price=prod.price,
                        status='CLOSED',
                    )
                    total += prod.price * qty

                tax = int(total * 0.1)
                Order.objects.filter(pk=order.pk).update(tax_amount=tax)

                if payment_methods:
                    receipt_counter += 1
                    POSTransaction.objects.create(
                        order=order,
                        payment_method=random.choice(payment_methods),
                        total_amount=total + tax + order.shipping_fee,
                        tax_amount=tax,
                        receipt_number=f'E{receipt_counter:06d}',
                        staff=random.choice(staff_list) if staff_list else None,
                        completed_at=order_time + timedelta(minutes=random.randint(1, 10)),
                    )
                ec_created += 1

        self.stdout.write(self.style.SUCCESS(f'  EC注文: {ec_created}件 (365日分)'))

        if options['ec_only']:
            self._print_summary()
            return

        # ── 店内注文追加 (91-365日前) ──
        instore_created = 0
        start_day = max(91, existing_days + 1) if existing_days > 0 else 91

        if start_day > 365:
            self.stdout.write('  店内注文: スキップ（既存データで365日以上）')
        else:
            for days_ago in range(365, start_day - 1, -1):
                order_date = now - timedelta(days=days_ago)
                month = order_date.month - 1
                weekday = order_date.weekday()

                base_orders = 4
                coeff = MONTHLY_COEFF[month] * WEEKDAY_COEFF[weekday]
                daily_instore = max(1, int(base_orders * coeff + random.uniform(-1, 2)))

                for _ in range(daily_instore):
                    hour = random.randint(13, 22)
                    order_time = order_date.replace(
                        hour=hour, minute=random.randint(0, 59), second=0,
                    )

                    channel = random.choice(['pos', 'table', 'reservation'])
                    table = random.choice(tables) if tables and channel == 'table' else None

                    # 顧客選択
                    r = random.random()
                    if r < 0.30:
                        customer = random.choice(regulars)
                    elif r < 0.65:
                        customer = random.choice(normals)
                    else:
                        customer = random.choice(occasionals)

                    order = Order.objects.create(
                        store=self.store,
                        table_seat=table,
                        table_label=table.label if table else '',
                        channel=channel,
                        status='CLOSED',
                        payment_status='paid',
                        customer_name=customer['name'],
                        customer_line_user_hash=customer['hash'],
                        discount_amount=0,
                    )
                    Order.objects.filter(pk=order.pk).update(created_at=order_time)

                    num_items = random.randint(1, 5)
                    total = 0
                    prods = instore_products if instore_products else ec_products
                    for prod in random.sample(prods, min(num_items, len(prods))):
                        qty = random.randint(1, 3) if prod.price < 1000 else 1
                        OrderItem.objects.create(
                            order=order, product=prod,
                            qty=qty, unit_price=prod.price,
                            status='CLOSED',
                        )
                        total += prod.price * qty

                    tax = int(total * 0.1)
                    Order.objects.filter(pk=order.pk).update(tax_amount=tax)

                    if payment_methods:
                        receipt_counter += 1
                        POSTransaction.objects.create(
                            order=order,
                            payment_method=random.choice(payment_methods),
                            total_amount=total + tax,
                            tax_amount=tax,
                            receipt_number=f'R{receipt_counter:06d}',
                            staff=random.choice(staff_list) if staff_list else None,
                            completed_at=order_time + timedelta(minutes=random.randint(30, 90)),
                        )
                    instore_created += 1

            self.stdout.write(self.style.SUCCESS(
                f'  店内注文: {instore_created}件 ({365}日前〜{start_day}日前)'))

        # ── 既存注文にも顧客ハッシュ付与 (RFM/コホート用) ──
        updated = self._backfill_customer_hashes(customer_pool)
        if updated:
            self.stdout.write(self.style.SUCCESS(f'  既存注文に顧客ハッシュ付与: {updated}件'))

        # ── 予約データも365日に拡張 ──
        schedule_created = self._extend_schedules()
        if schedule_created:
            self.stdout.write(self.style.SUCCESS(f'  予約: {schedule_created}件追加'))

        # ── 来客データも365日に拡張 ──
        visitor_created = self._extend_visitor_counts()
        if visitor_created:
            self.stdout.write(self.style.SUCCESS(f'  来客数: {visitor_created}件追加'))

        self._print_summary()

    def _reset(self):
        """EC注文と追加店内注文を削除"""
        ec_deleted, _ = Order.objects.filter(
            store=self.store, channel='ec',
        ).delete()
        self.stdout.write(f'  リセット: EC注文 {ec_deleted}件削除')

    def _backfill_customer_hashes(self, customer_pool):
        """既存注文に顧客ハッシュがなければ付与"""
        orders_no_hash = Order.objects.filter(
            store=self.store,
            customer_line_user_hash__isnull=True,
        ) | Order.objects.filter(
            store=self.store,
            customer_line_user_hash='',
        )

        count = 0
        for order in orders_no_hash.iterator():
            if order.customer_name:
                matching = [c for c in customer_pool if c['name'] == order.customer_name]
                if matching:
                    customer = matching[0]
                else:
                    customer = random.choice(customer_pool)
            else:
                customer = random.choice(customer_pool)

            Order.objects.filter(pk=order.pk).update(
                customer_name=customer['name'] if not order.customer_name else order.customer_name,
                customer_line_user_hash=customer['hash'],
            )
            count += 1

        return count

    def _extend_schedules(self):
        """予約データを365日分に拡張"""
        now = timezone.now()
        oldest_schedule = Schedule.objects.filter(
            memo='モックデータ'
        ).aggregate(oldest=Min('start'))['oldest']

        if oldest_schedule and (now - oldest_schedule).days >= 350:
            return 0

        staff_list = list(Staff.objects.filter(
            store=self.store, staff_type='fortune_teller',
        ))
        if not staff_list:
            return 0

        created = 0
        for days_offset in range(-365, -90):
            target = now + timedelta(days=days_offset)
            daily_bookings = random.randint(2, 5)
            if target.weekday() >= 4:
                daily_bookings += random.randint(1, 3)

            month = target.month - 1
            daily_bookings = max(1, int(daily_bookings * MONTHLY_COEFF[month]))

            for _ in range(daily_bookings):
                staff = random.choice(staff_list)
                hour = random.randint(13, 21)
                start = target.replace(hour=hour, minute=0, second=0, microsecond=0)
                end = start + timedelta(minutes=random.choice([30, 60]))

                is_cancelled = random.random() < 0.08

                Schedule.objects.create(
                    staff=staff,
                    start=start,
                    end=end,
                    customer_name=random.choice(CUSTOMER_NAMES),
                    is_cancelled=is_cancelled,
                    price=staff.price,
                    memo='モックデータ',
                    booking_channel=random.choice(['line', 'line', 'line', 'email']),
                )
                created += 1

        return created

    def _extend_visitor_counts(self):
        """来客数データを365日分に拡張"""
        now = timezone.now()
        oldest_vc = VisitorCount.objects.filter(
            store=self.store,
        ).aggregate(oldest=Min('date'))['oldest']

        if oldest_vc and (now.date() - oldest_vc).days >= 350:
            return 0

        created = 0
        for days_ago in range(365, 90, -1):
            target_date = (now - timedelta(days=days_ago)).date()
            weekday = target_date.weekday()
            month = target_date.month - 1

            if VisitorCount.objects.filter(
                store=self.store, date=target_date,
            ).exists():
                continue

            for hour in range(9, 24):
                if hour < 13:
                    base = 0
                else:
                    base = 3 if weekday < 4 else 5
                    if 19 <= hour <= 22:
                        base = int(base * 2.5)
                    elif 15 <= hour <= 17:
                        base = int(base * 1.3)
                    if weekday >= 4:
                        base = int(base * 1.5)

                base = int(base * MONTHLY_COEFF[month])
                pir = max(0, base + random.randint(-2, 4))
                visitors = max(0, int(pir * random.uniform(0.6, 0.9)))
                orders_h = max(0, int(visitors * random.uniform(0.3, 0.7)))

                VisitorCount.objects.create(
                    store=self.store, date=target_date, hour=hour,
                    pir_count=pir, estimated_visitors=visitors,
                    order_count=orders_h,
                )
                created += 1

        return created

    def _print_summary(self):
        """最終サマリー"""
        total_orders = Order.objects.filter(store=self.store).count()
        ec_orders = Order.objects.filter(store=self.store, channel='ec').count()
        pos_orders = Order.objects.filter(store=self.store, channel='pos').count()
        table_orders = Order.objects.filter(store=self.store, channel='table').count()
        reservation_orders = Order.objects.filter(store=self.store, channel='reservation').count()

        oldest = Order.objects.filter(store=self.store).aggregate(
            oldest=Min('created_at'))['oldest']
        days_span = (timezone.now() - oldest).days if oldest else 0

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== 売上データサマリー ==='))
        self.stdout.write(f'  期間: {days_span}日分')
        self.stdout.write(f'  総注文数: {total_orders}件')
        self.stdout.write(f'    EC: {ec_orders}件')
        self.stdout.write(f'    POS: {pos_orders}件')
        self.stdout.write(f'    テーブル: {table_orders}件')
        self.stdout.write(f'    予約: {reservation_orders}件')

        unique_customers = Order.objects.filter(
            store=self.store,
            customer_line_user_hash__isnull=False,
        ).exclude(customer_line_user_hash='').values(
            'customer_line_user_hash',
        ).distinct().count()
        self.stdout.write(f'  ユニーク顧客数: {unique_customers}名')
