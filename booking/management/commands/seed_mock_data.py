"""
モックデータ投入コマンド
既存データ（Store, Staff, IoTDevice等）はそのまま保持し、
空のモデルにリアルなテストデータを投入する。

Usage:
    python manage.py seed_mock_data
    python manage.py seed_mock_data --reset  # 既存モックデータを削除してから再投入
"""
import random
import uuid
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone

from booking.models import (
    Store, Staff, Schedule, Company, Notice, Media,
    Category, Product, ProductTranslation,
    Order, OrderItem, StockMovement,
    TableSeat, PaymentMethod, StoreScheduleConfig,
    ShiftPeriod, ShiftRequest, ShiftAssignment, ShiftTemplate,
    ShiftPublishHistory,
    AdminTheme, SiteSettings, HomepageCustomBlock, ExternalLink,
    HeroBanner, BannerAd,
    EmploymentContract, WorkAttendance, PayrollPeriod, PayrollEntry,
    PayrollDeduction, SalaryStructure,
    IoTDevice, VentilationAutoControl,
    VisitorCount, VisitorAnalyticsConfig,
    DashboardLayout, SystemConfig,
    POSTransaction,
)


class Command(BaseCommand):
    help = 'シーシャ＆占いサロン向けモックデータを投入'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='このコマンドで作ったモックデータを削除してから再投入',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self._reset()

        self.store = Store.objects.first()
        if not self.store:
            self.stderr.write('Store が存在しません。先に Store を作成してください。')
            return

        self.stdout.write(f'対象店舗: {self.store.name} (ID={self.store.id})')

        self._seed_company()
        self._seed_notices()
        self._seed_media()
        self._seed_extra_staff()
        self._seed_categories_and_products()
        self._seed_payment_methods()
        self._seed_store_schedule_config()
        self._seed_table_seats()
        self._seed_shift_templates()
        self._seed_shift_periods()
        self._seed_employment_contracts()
        self._seed_orders()
        self._seed_work_attendance()
        self._seed_salary_structure()
        self._seed_payroll()
        self._seed_admin_theme()
        self._seed_homepage_blocks()
        self._seed_external_links()
        self._seed_visitor_counts()
        self._seed_ventilation_auto_control()
        self._seed_dashboard_layouts()
        self._seed_system_configs()

        self.stdout.write(self.style.SUCCESS('モックデータ投入完了'))

    # ─────────────────────────────────────────────
    # Reset
    # ─────────────────────────────────────────────
    def _reset(self):
        self.stdout.write('モックデータを削除中...')
        # 削除順序は FK 依存を考慮
        PayrollDeduction.objects.all().delete()
        PayrollEntry.objects.all().delete()
        PayrollPeriod.objects.all().delete()
        POSTransaction.objects.all().delete()
        OrderItem.objects.all().delete()
        StockMovement.objects.all().delete()
        # 既存注文は保持（ID=1 は実データ）
        Order.objects.exclude(id=1).delete()
        WorkAttendance.objects.all().delete()
        ShiftPublishHistory.objects.all().delete()
        ShiftAssignment.objects.all().delete()
        ShiftRequest.objects.all().delete()
        ShiftPeriod.objects.all().delete()
        ShiftTemplate.objects.all().delete()
        EmploymentContract.objects.all().delete()
        ProductTranslation.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        PaymentMethod.objects.all().delete()
        VentilationAutoControl.objects.all().delete()
        VisitorCount.objects.all().delete()
        VisitorAnalyticsConfig.objects.all().delete()
        Notice.objects.all().delete()
        Media.objects.all().delete()
        Company.objects.all().delete()
        HomepageCustomBlock.objects.all().delete()
        ExternalLink.objects.all().delete()
        SalaryStructure.objects.all().delete()
        AdminTheme.objects.all().delete()
        StoreScheduleConfig.objects.all().delete()
        DashboardLayout.objects.all().delete()
        SystemConfig.objects.all().delete()
        # 追加スタッフ（既存1名は保持）
        Staff.objects.filter(name__in=[
            '星野 ルナ', '月見 アカリ', '水瀬 ソラ', '朝霧 ヒカル',
        ]).delete()
        User.objects.filter(username__in=[
            'hoshino', 'tsukimi', 'minase', 'asagiri',
        ]).delete()
        self.stdout.write(self.style.SUCCESS('既存モックデータを削除しました'))

    # ─────────────────────────────────────────────
    # Company
    # ─────────────────────────────────────────────
    def _seed_company(self):
        if Company.objects.exists():
            self.stdout.write('  Company: 既存データあり → skip')
            return
        Company.objects.create(
            name='株式会社タイムバイバイ',
            address='東京都渋谷区道玄坂1-2-3 シーシャビル5F',
            tel='03-1234-5678',
        )
        self.stdout.write(self.style.SUCCESS('  Company: 作成完了'))

    # ─────────────────────────────────────────────
    # Notice
    # ─────────────────────────────────────────────
    def _seed_notices(self):
        if Notice.objects.exists():
            self.stdout.write('  Notice: 既存データあり → skip')
            return
        notices = [
            ('年末年始の営業について', 'https://timebaibai.com/news/1',
             '12/31〜1/3は休業とさせていただきます。1/4より通常営業です。'),
            ('新メニュー「ヒーリングシーシャ」登場', 'https://timebaibai.com/news/2',
             'アロマの香りと占いを同時に楽しめる新メニューが登場しました。'),
            ('スタッフ募集のお知らせ', 'https://timebaibai.com/news/3',
             '占い師・シーシャスタッフ募集中です。未経験OK、研修あり。'),
        ]
        for title, link, content in notices:
            Notice.objects.create(title=title, link=link, content=content)
        self.stdout.write(self.style.SUCCESS('  Notice: 3件作成'))

    # ─────────────────────────────────────────────
    # Media
    # ─────────────────────────────────────────────
    def _seed_media(self):
        if Media.objects.exists():
            self.stdout.write('  Media: 既存データあり → skip')
            return
        medias = [
            ('https://www.instagram.com/p/example1/', '渋谷店の内装が完成！'),
            ('https://www.instagram.com/p/example2/', '新しいシーシャフレーバー入荷'),
        ]
        for link, title in medias:
            Media.objects.create(link=link, title=title, description=f'{title}の詳細はこちら')
        self.stdout.write(self.style.SUCCESS('  Media: 2件作成'))

    # ─────────────────────────────────────────────
    # Extra Staff (占い師を追加)
    # ─────────────────────────────────────────────
    def _seed_extra_staff(self):
        new_staff_data = [
            ('hoshino', '星野 ルナ', 'fortune_teller', 3000, 'タロット・西洋占星術を得意とする占い師。'),
            ('tsukimi', '月見 アカリ', 'fortune_teller', 2500, '手相・数秘術のスペシャリスト。'),
            ('minase', '水瀬 ソラ', 'store_staff', 0, 'シーシャ調合の達人。お気に入りのフレーバーを提案します。'),
            ('asagiri', '朝霧 ヒカル', 'fortune_teller', 4000, '霊感タロット・オーラリーディング。予約が取れない人気占い師。'),
        ]
        created = 0
        for username, name, staff_type, price, intro in new_staff_data:
            if Staff.objects.filter(name=name).exists():
                continue
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'is_staff': True},
            )
            if not user.has_usable_password():
                user.set_password('mock1234')
                user.save()

            Staff.objects.create(
                user=user, store=self.store, name=name,
                staff_type=staff_type, price=price,
                introduction=intro,
                is_recommended=(staff_type == 'fortune_teller'),
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f'  Staff: {created}名追加'))

    # ─────────────────────────────────────────────
    # Category & Product (シーシャ＆占い商品)
    # ─────────────────────────────────────────────
    def _seed_categories_and_products(self):
        if Category.objects.filter(store=self.store).exists():
            self.stdout.write('  Category/Product: 既存データあり → skip')
            return

        categories_products = {
            'シーシャ': [
                ('SH-001', 'ダブルアップル', 'クラシックなダブルアップル。甘くフルーティ。', 1800, 50),
                ('SH-002', 'ブルーベリーミント', 'ブルーベリーとミントの爽やかブレンド。', 1800, 40),
                ('SH-003', 'マンゴーアイス', 'トロピカルマンゴーにクールメンソール。', 2000, 30),
                ('SH-004', 'グレープフリーズ', '巨峰のような濃厚グレープ＋氷感。', 2000, 35),
                ('SH-005', 'チャイラテ', 'スパイシーなチャイ風味。冬の定番。', 2200, 20),
                ('SH-006', 'ピーチパッション', '桃×パッションフルーツの南国MIX。', 1800, 45),
            ],
            'ドリンク': [
                ('DR-001', 'チャイティー', '自家製スパイスのチャイティー', 600, 100),
                ('DR-002', 'アイスレモネード', '自家製レモネード（氷たっぷり）', 550, 100),
                ('DR-003', 'ホットココア', '濃厚ホットチョコレート', 650, 80),
                ('DR-004', 'ジャスミンティー', '香り高いジャスミンティー', 500, 100),
                ('DR-005', 'コーラ', 'コカ・コーラ', 400, 200),
                ('DR-006', 'ジンジャーエール', 'ウィルキンソン', 400, 150),
            ],
            'フード': [
                ('FD-001', 'ナチョス', 'チーズたっぷりナチョス', 800, 30),
                ('FD-002', 'フムス&ピタ', '自家製フムスとピタパン', 700, 25),
                ('FD-003', 'ミックスナッツ', 'ローストミックスナッツ', 500, 50),
                ('FD-004', 'ドライフルーツ盛り合わせ', '5種のドライフルーツ', 600, 40),
            ],
            '占いメニュー': [
                ('FT-001', 'タロット占い（20分）', 'ケルト十字スプレッドで深く読み解きます', 3000, 999),
                ('FT-002', 'タロット占い（40分）', 'じっくり複数の質問にお答えします', 5000, 999),
                ('FT-003', '手相鑑定', '両手の手相を総合的に鑑定', 2500, 999),
                ('FT-004', '西洋占星術', '出生ホロスコープチャートを作成・解説', 4000, 999),
                ('FT-005', 'オーラリーディング', 'あなたのオーラの色と意味をお伝えします', 3500, 999),
                ('FT-006', 'ヒーリングシーシャセット', 'シーシャ＋占い20分のお得セット', 4500, 999),
            ],
            'グッズ': [
                ('GD-001', 'パワーストーンブレスレット', 'オリジナル天然石ブレスレット', 3800, 15),
                ('GD-002', 'タロットカード（ライダー版）', '初心者にもおすすめの定番デッキ', 2800, 10),
                ('GD-003', 'ホワイトセージ', '浄化用ホワイトセージバンドル', 1200, 20),
                ('GD-004', 'オリジナルお香セット', '5種類のお香スティック', 1500, 25),
            ],
        }

        en_translations = {
            'ダブルアップル': ('Double Apple', 'Classic double apple. Sweet and fruity.'),
            'ブルーベリーミント': ('Blueberry Mint', 'Refreshing blueberry and mint blend.'),
            'マンゴーアイス': ('Mango Ice', 'Tropical mango with cool menthol.'),
            'チャイティー': ('Chai Tea', 'Homemade spiced chai tea.'),
            'タロット占い（20分）': ('Tarot Reading (20min)', 'Celtic cross spread deep reading.'),
        }

        for sort_order, (cat_name, products) in enumerate(categories_products.items()):
            cat = Category.objects.create(
                store=self.store, name=cat_name, sort_order=sort_order,
            )
            for sku, name, desc, price, stock in products:
                p = Product.objects.create(
                    store=self.store, category=cat,
                    sku=sku, name=name, description=desc,
                    price=price, stock=stock,
                    is_active=True, is_ec_visible=(cat_name != '占いメニュー'),
                    popularity=random.randint(0, 100),
                    margin_rate=round(random.uniform(0.2, 0.6), 2),
                )
                if name in en_translations:
                    en_name, en_desc = en_translations[name]
                    ProductTranslation.objects.create(
                        product=p, lang='en', name=en_name, description=en_desc,
                    )

        total = Product.objects.filter(store=self.store).count()
        self.stdout.write(self.style.SUCCESS(f'  Category: {len(categories_products)}件, Product: {total}件作成'))

    # ─────────────────────────────────────────────
    # PaymentMethod
    # ─────────────────────────────────────────────
    def _seed_payment_methods(self):
        if PaymentMethod.objects.filter(store=self.store).exists():
            self.stdout.write('  PaymentMethod: 既存データあり → skip')
            return
        methods = [
            ('cash', '現金', 0),
            ('paypay', 'PayPay', 1),
            ('coiney', 'クレジットカード（Coiney）', 2),
            ('ic', '交通系IC / 電子マネー', 3),
        ]
        for method_type, display_name, sort_order in methods:
            PaymentMethod.objects.create(
                store=self.store, method_type=method_type,
                display_name=display_name, is_enabled=True,
                sort_order=sort_order,
            )
        self.stdout.write(self.style.SUCCESS('  PaymentMethod: 4件作成'))

    # ─────────────────────────────────────────────
    # StoreScheduleConfig
    # ─────────────────────────────────────────────
    def _seed_store_schedule_config(self):
        if StoreScheduleConfig.objects.filter(store=self.store).exists():
            self.stdout.write('  StoreScheduleConfig: 既存データあり → skip')
            return
        StoreScheduleConfig.objects.create(
            store=self.store, open_hour=13, close_hour=23, slot_duration=60,
        )
        self.stdout.write(self.style.SUCCESS('  StoreScheduleConfig: 作成完了'))

    # ─────────────────────────────────────────────
    # TableSeat（既存2席に追加）
    # ─────────────────────────────────────────────
    def _seed_table_seats(self):
        existing = TableSeat.objects.filter(store=self.store).count()
        if existing >= 5:
            self.stdout.write('  TableSeat: 十分なデータあり → skip')
            return
        labels = ['A1', 'A2', 'B1', 'B2', 'B3', 'VIP']
        created = 0
        for label in labels:
            if not TableSeat.objects.filter(store=self.store, label=label).exists():
                TableSeat.objects.create(store=self.store, label=label, is_active=True)
                created += 1
        self.stdout.write(self.style.SUCCESS(f'  TableSeat: {created}席追加'))

    # ─────────────────────────────────────────────
    # ShiftTemplate
    # ─────────────────────────────────────────────
    def _seed_shift_templates(self):
        if ShiftTemplate.objects.filter(store=self.store).exists():
            self.stdout.write('  ShiftTemplate: 既存データあり → skip')
            return
        templates = [
            ('昼シフト', time(13, 0), time(18, 0), '#3B82F6'),
            ('夜シフト', time(18, 0), time(23, 0), '#8B5CF6'),
            ('通しシフト', time(13, 0), time(23, 0), '#10B981'),
        ]
        for i, (name, start, end, color) in enumerate(templates):
            ShiftTemplate.objects.create(
                store=self.store, name=name,
                start_time=start, end_time=end,
                color=color, sort_order=i,
            )
        self.stdout.write(self.style.SUCCESS('  ShiftTemplate: 3件作成'))

    # ─────────────────────────────────────────────
    # ShiftPeriod + ShiftRequest + ShiftAssignment
    # ─────────────────────────────────────────────
    def _seed_shift_periods(self):
        if ShiftPeriod.objects.filter(store=self.store).exists():
            self.stdout.write('  ShiftPeriod: 既存データあり → skip')
            return

        now = timezone.now()
        staff_list = list(Staff.objects.filter(store=self.store))
        if not staff_list:
            self.stdout.write('  ShiftPeriod: スタッフなし → skip')
            return

        # 今月と来月の2期間作成
        for month_offset in [0, 1]:
            target = (now.replace(day=1) + timedelta(days=32 * month_offset)).replace(day=1)
            period = ShiftPeriod.objects.create(
                store=self.store,
                year_month=target.date(),
                deadline=timezone.make_aware(
                    target.replace(day=25, hour=23, minute=59).replace(tzinfo=None)
                ) if month_offset == 1 else now - timedelta(days=5),
                status='scheduled' if month_offset == 0 else 'open',
            )

            # 各スタッフのシフト希望＆割当を生成
            for staff in staff_list:
                days_in_month = 28  # 簡略化
                for day in range(1, days_in_month + 1):
                    try:
                        shift_date = target.replace(day=day).date()
                    except ValueError:
                        continue

                    # 週2〜4日程度の出勤
                    if random.random() < 0.45:
                        continue

                    start_h = random.choice([13, 14, 15, 18])
                    end_h = min(start_h + random.choice([5, 6, 8, 10]), 23)

                    ShiftRequest.objects.create(
                        period=period, staff=staff,
                        date=shift_date, start_hour=start_h, end_hour=end_h,
                        preference=random.choice(['available', 'preferred']),
                    )

                    if month_offset == 0:  # 今月は割当済
                        ShiftAssignment.objects.create(
                            period=period, staff=staff,
                            date=shift_date, start_hour=start_h, end_hour=end_h,
                            color=random.choice(['#3B82F6', '#8B5CF6', '#10B981']),
                        )

            if month_offset == 0:
                ShiftPublishHistory.objects.create(
                    period=period,
                    assignment_count=ShiftAssignment.objects.filter(period=period).count(),
                    note='自動生成（モックデータ）',
                )

        req_count = ShiftRequest.objects.filter(period__store=self.store).count()
        assign_count = ShiftAssignment.objects.filter(period__store=self.store).count()
        self.stdout.write(self.style.SUCCESS(
            f'  ShiftPeriod: 2件, ShiftRequest: {req_count}件, ShiftAssignment: {assign_count}件'
        ))

    # ─────────────────────────────────────────────
    # EmploymentContract
    # ─────────────────────────────────────────────
    def _seed_employment_contracts(self):
        if EmploymentContract.objects.exists():
            self.stdout.write('  EmploymentContract: 既存データあり → skip')
            return
        staff_list = Staff.objects.filter(store=self.store)
        for staff in staff_list:
            is_fortune = staff.staff_type == 'fortune_teller'
            EmploymentContract.objects.create(
                staff=staff,
                employment_type='part_time',
                pay_type='hourly',
                hourly_rate=1500 if not is_fortune else 2000,
                commute_allowance=500,
                birth_date=date(1990, random.randint(1, 12), random.randint(1, 28)),
                contract_start=date(2024, 4, 1),
                is_active=True,
            )
        self.stdout.write(self.style.SUCCESS(f'  EmploymentContract: {staff_list.count()}件作成'))

    # ─────────────────────────────────────────────
    # Order & OrderItem (過去30日分のリアルな注文)
    # ─────────────────────────────────────────────
    def _seed_orders(self):
        existing = Order.objects.filter(store=self.store).count()
        if existing >= 10:
            self.stdout.write('  Order: 十分なデータあり → skip')
            return

        products = list(Product.objects.filter(store=self.store, is_active=True))
        if not products:
            self.stdout.write('  Order: 商品なし → skip')
            return

        tables = list(TableSeat.objects.filter(store=self.store, is_active=True))
        staff_list = list(Staff.objects.filter(store=self.store))
        payment_methods = list(PaymentMethod.objects.filter(store=self.store, is_enabled=True))

        now = timezone.now()
        order_count = 0
        receipt_counter = 1000

        for days_ago in range(30, 0, -1):
            order_date = now - timedelta(days=days_ago)
            # 1日あたり3〜8件の注文
            daily_orders = random.randint(3, 8)

            for _ in range(daily_orders):
                hour = random.randint(13, 22)
                order_time = order_date.replace(
                    hour=hour, minute=random.randint(0, 59), second=0
                )

                table = random.choice(tables) if tables else None
                order = Order.objects.create(
                    store=self.store,
                    table_seat=table,
                    table_label=table.label if table else '',
                    status='CLOSED',
                    payment_status='paid',
                    created_at=order_time,
                )
                # created_at を上書き（auto_now_add対策）
                Order.objects.filter(pk=order.pk).update(created_at=order_time)

                # 1注文あたり1〜4アイテム
                num_items = random.randint(1, 4)
                total = 0
                for prod in random.sample(products, min(num_items, len(products))):
                    qty = random.randint(1, 3) if prod.price < 1000 else 1
                    OrderItem.objects.create(
                        order=order, product=prod,
                        qty=qty, unit_price=prod.price,
                        status='CLOSED',
                    )
                    total += prod.price * qty

                tax = int(total * 0.1)
                Order.objects.filter(pk=order.pk).update(tax_amount=tax)

                # POS Transaction
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

                order_count += 1

        self.stdout.write(self.style.SUCCESS(f'  Order: {order_count}件作成（POS含む）'))

    # ─────────────────────────────────────────────
    # WorkAttendance (過去30日分)
    # ─────────────────────────────────────────────
    def _seed_work_attendance(self):
        if WorkAttendance.objects.exists():
            self.stdout.write('  WorkAttendance: 既存データあり → skip')
            return

        staff_list = list(Staff.objects.filter(store=self.store))
        now = timezone.now()
        created = 0

        for staff in staff_list:
            for days_ago in range(30, 0, -1):
                target_date = (now - timedelta(days=days_ago)).date()
                # 週3〜4日出勤
                if random.random() < 0.45:
                    continue

                start_h = random.choice([13, 14, 18])
                end_h = min(start_h + random.choice([5, 6, 8]), 23)
                regular = (end_h - start_h) * 60
                overtime = max(0, regular - 480)  # 8h超は残業
                late_night = max(0, end_h - 22) * 60  # 22時以降

                WorkAttendance.objects.create(
                    staff=staff,
                    date=target_date,
                    clock_in=time(start_h, 0),
                    clock_out=time(end_h, 0),
                    regular_minutes=regular - overtime,
                    overtime_minutes=overtime,
                    late_night_minutes=late_night,
                    break_minutes=30 if regular > 360 else 0,
                    source='shift',
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f'  WorkAttendance: {created}件作成'))

    # ─────────────────────────────────────────────
    # SalaryStructure
    # ─────────────────────────────────────────────
    def _seed_salary_structure(self):
        if SalaryStructure.objects.filter(store=self.store).exists():
            self.stdout.write('  SalaryStructure: 既存データあり → skip')
            return
        SalaryStructure.objects.create(store=self.store)
        self.stdout.write(self.style.SUCCESS('  SalaryStructure: 作成完了（デフォルト値）'))

    # ─────────────────────────────────────────────
    # Payroll (先月分)
    # ─────────────────────────────────────────────
    def _seed_payroll(self):
        if PayrollPeriod.objects.filter(store=self.store).exists():
            self.stdout.write('  Payroll: 既存データあり → skip')
            return

        now = timezone.now()
        last_month = (now.replace(day=1) - timedelta(days=1))
        period_start = last_month.replace(day=1).date()
        period_end = last_month.date()

        period = PayrollPeriod.objects.create(
            store=self.store,
            year_month=period_start.strftime('%Y-%m'),
            period_start=period_start,
            period_end=period_end,
            status='confirmed',
            payment_date=now.date(),
        )

        staff_list = Staff.objects.filter(store=self.store)
        for staff in staff_list:
            contract = getattr(staff, 'employment_contract', None)
            hourly = contract.hourly_rate if contract else 1200

            attendances = WorkAttendance.objects.filter(
                staff=staff,
                date__gte=period_start,
                date__lte=period_end,
            )
            work_days = attendances.count()
            total_regular = sum(a.regular_minutes for a in attendances) / 60
            total_overtime = sum(a.overtime_minutes for a in attendances) / 60
            total_late = sum(a.late_night_minutes for a in attendances) / 60

            base_pay = int(total_regular * hourly)
            overtime_pay = int(total_overtime * hourly * 1.25)
            late_night_pay = int(total_late * hourly * 1.35)
            gross = base_pay + overtime_pay + late_night_pay
            if contract:
                gross += contract.commute_allowance * work_days

            # 簡易控除計算
            income_tax = int(gross * 0.05)
            employment_ins = int(gross * 0.006)
            total_deductions = income_tax + employment_ins
            net = gross - total_deductions

            entry = PayrollEntry.objects.create(
                period=period, staff=staff, contract=contract,
                total_work_days=work_days,
                total_regular_hours=Decimal(str(round(total_regular, 1))),
                total_overtime_hours=Decimal(str(round(total_overtime, 1))),
                total_late_night_hours=Decimal(str(round(total_late, 1))),
                base_pay=base_pay,
                overtime_pay=overtime_pay,
                late_night_pay=late_night_pay,
                allowances=contract.commute_allowance * work_days if contract else 0,
                gross_pay=gross,
                total_deductions=total_deductions,
                net_pay=net,
            )

            PayrollDeduction.objects.create(
                entry=entry, deduction_type='income_tax', amount=income_tax,
            )
            PayrollDeduction.objects.create(
                entry=entry, deduction_type='employment_insurance', amount=employment_ins,
            )

        self.stdout.write(self.style.SUCCESS(f'  Payroll: {staff_list.count()}名分作成'))

    # ─────────────────────────────────────────────
    # AdminTheme
    # ─────────────────────────────────────────────
    def _seed_admin_theme(self):
        if AdminTheme.objects.filter(store=self.store).exists():
            self.stdout.write('  AdminTheme: 既存データあり → skip')
            return
        AdminTheme.objects.create(
            store=self.store,
            primary_color='#8c876c',
            secondary_color='#f1f0ec',
        )
        self.stdout.write(self.style.SUCCESS('  AdminTheme: 作成完了'))

    # ─────────────────────────────────────────────
    # HomepageCustomBlock
    # ─────────────────────────────────────────────
    def _seed_homepage_blocks(self):
        if HomepageCustomBlock.objects.exists():
            self.stdout.write('  HomepageCustomBlock: 既存データあり → skip')
            return
        blocks = [
            ('初回限定キャンペーン',
             '<div style="background:#FEF3C7;padding:16px;border-radius:8px;text-align:center;">'
             '<h3>初回来店限定！シーシャ＋占い20分セットが <span style="color:#DC2626">20%OFF</span></h3>'
             '<p>LINEでご予約の方限定。この画面を見せてください。</p></div>',
             'above_cards', 0),
            ('お客様の声',
             '<div style="padding:16px;"><h3>お客様の声</h3>'
             '<blockquote>"初めてのシーシャと占い、最高の体験でした！" — A.K様</blockquote>'
             '<blockquote>"星野先生のタロット、当たりすぎて怖いくらい" — M.S様</blockquote></div>',
             'below_cards', 1),
        ]
        for title, content, position, sort_order in blocks:
            HomepageCustomBlock.objects.create(
                title=title, content=content,
                position=position, sort_order=sort_order, is_active=True,
            )
        self.stdout.write(self.style.SUCCESS('  HomepageCustomBlock: 2件作成'))

    # ─────────────────────────────────────────────
    # ExternalLink
    # ─────────────────────────────────────────────
    def _seed_external_links(self):
        if ExternalLink.objects.exists():
            self.stdout.write('  ExternalLink: 既存データあり → skip')
            return
        links = [
            ('Instagram', 'https://www.instagram.com/timebaibai/', 'お店の最新情報はこちら', 0),
            ('LINE公式アカウント', 'https://lin.ee/example', 'ご予約はLINEが便利です', 1),
            ('Googleマップ', 'https://maps.google.com/?q=渋谷区道玄坂', '店舗へのアクセス', 2),
        ]
        for title, url, desc, sort in links:
            ExternalLink.objects.create(
                title=title, url=url, description=desc,
                sort_order=sort, is_active=True, open_in_new_tab=True,
            )
        self.stdout.write(self.style.SUCCESS('  ExternalLink: 3件作成'))

    # ─────────────────────────────────────────────
    # VisitorCount (過去30日分)
    # ─────────────────────────────────────────────
    def _seed_visitor_counts(self):
        if VisitorCount.objects.filter(store=self.store).exists():
            self.stdout.write('  VisitorCount: 既存データあり → skip')
            return

        now = timezone.now()
        created = 0
        for days_ago in range(30, 0, -1):
            target_date = (now - timedelta(days=days_ago)).date()
            weekday = target_date.weekday()  # 0=Mon ... 6=Sun

            for hour in range(13, 24):
                # 金土は混む、平日昼は少ない
                base = 3 if weekday < 4 else 6
                if hour >= 19 and hour <= 22:
                    base *= 2  # ゴールデンタイム
                if weekday >= 4:
                    base = int(base * 1.5)

                pir = max(0, base + random.randint(-2, 5))
                visitors = max(0, int(pir * 0.7))
                orders_h = max(0, int(visitors * random.uniform(0.3, 0.8)))

                VisitorCount.objects.create(
                    store=self.store, date=target_date, hour=hour,
                    pir_count=pir, estimated_visitors=visitors,
                    order_count=orders_h,
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(f'  VisitorCount: {created}件作成'))

    # ─────────────────────────────────────────────
    # VentilationAutoControl（SwitchBotダミー設定）
    # ─────────────────────────────────────────────
    def _seed_ventilation_auto_control(self):
        if VentilationAutoControl.objects.exists():
            self.stdout.write('  VentilationAutoControl: 既存データあり → skip')
            return

        device = IoTDevice.objects.filter(store=self.store).first()
        if not device:
            self.stdout.write('  VentilationAutoControl: IoTDeviceなし → skip')
            return

        VentilationAutoControl.objects.create(
            device=device,
            name='換気扇自動制御（メイン）',
            is_active=False,  # ダミーなので無効
            threshold_on=400,
            threshold_off=200,
            consecutive_count=3,
            switchbot_token='DUMMY_TOKEN_REPLACE_ME',
            switchbot_secret='DUMMY_SECRET_REPLACE_ME',
            switchbot_device_id='DUMMY_DEVICE_ID',
            cooldown_seconds=60,
        )
        self.stdout.write(self.style.SUCCESS('  VentilationAutoControl: 1件作成（無効状態）'))

    # ─────────────────────────────────────────────
    # DashboardLayout
    # ─────────────────────────────────────────────
    def _seed_dashboard_layouts(self):
        if DashboardLayout.objects.exists():
            self.stdout.write('  DashboardLayout: 既存データあり → skip')
            return
        admin_user = User.objects.filter(is_superuser=True).first()
        if admin_user:
            DashboardLayout.objects.create(
                user=admin_user,
                layout_json=[
                    {'widget': 'today_orders', 'x': 0, 'y': 0, 'w': 6, 'h': 4},
                    {'widget': 'visitor_chart', 'x': 6, 'y': 0, 'w': 6, 'h': 4},
                    {'widget': 'recent_iot', 'x': 0, 'y': 4, 'w': 12, 'h': 4},
                ],
            )
            self.stdout.write(self.style.SUCCESS('  DashboardLayout: 1件作成'))

    # ─────────────────────────────────────────────
    # SystemConfig
    # ─────────────────────────────────────────────
    def _seed_system_configs(self):
        if SystemConfig.objects.exists():
            self.stdout.write('  SystemConfig: 既存データあり → skip')
            return
        configs = [
            ('maintenance_mode', 'false'),
            ('max_reservations_per_day', '20'),
            ('auto_cancel_minutes', '15'),
            ('line_notify_enabled', 'true'),
        ]
        for key, value in configs:
            SystemConfig.objects.create(key=key, value=value)
        self.stdout.write(self.style.SUCCESS(f'  SystemConfig: {len(configs)}件作成'))
