"""当日分＋過去分のデモデータを自動生成するコマンド。

Celeryタスクから30分毎に呼ばれ、現在時刻までの当日デモデータを生成する。
--seed オプションで過去90日分の履歴データも一括生成する。

Usage:
    python manage.py generate_live_demo_data          # 当日分のみ
    python manage.py generate_live_demo_data --seed    # 過去90日分+当日分
"""
import hashlib
import random
from datetime import date, timedelta, time as dt_time

from django.core.management.base import BaseCommand
from django.utils import timezone

from booking.models import (
    Store, Staff, Product, Order, OrderItem,
    Schedule, VisitorCount, SiteSettings,
    WorkAttendance, AttendanceStamp,
    ShiftPeriod, ShiftAssignment,
    CustomerFeedback, BusinessInsight,
)

# --- 定数 ---
CUSTOMER_NAMES = [
    '田中 花子', '佐藤 太郎', '鈴木 一郎', '高橋 美咲',
    '渡辺 健', '伊藤 さくら', '山本 大輔', '中村 あかり',
    '小林 翔太', '加藤 凛', '吉田 陽子', '山田 拓海',
    '松本 美月', '井上 蓮', '木村 結衣', '林 悠斗',
]
CUSTOMER_HASHES = [
    hashlib.sha256(f'demo_customer_{i}'.encode()).hexdigest()[:16]
    for i in range(20)
]
SHIFT_PATTERNS = [
    (9, 15, '#10B981'),   # 早番 green
    (14, 21, '#6366F1'),  # 遅番 indigo
    (9, 18, '#3B82F6'),   # 通し blue
    (10, 16, '#F59E0B'),  # 中番 amber
]
CHANNELS = ['pos', 'table', 'reservation', 'ec']
FEEDBACK_COMMENTS = {
    'positive': [
        '素晴らしい接客でした！また来ます。',
        '占いの結果がとても当たっていて驚きました。',
        'スタッフの方がとても親切で安心できました。',
        '店内の雰囲気がとても良かったです。',
        '友人にもおすすめしたいです。',
    ],
    'neutral': [
        '普通に良かったです。',
        '可もなく不可もなくといった感じです。',
        '待ち時間がもう少し短いと嬉しいです。',
    ],
    'negative': [
        '予約時間に遅れがありました。',
        '説明が少しわかりにくかったです。',
        '期待していたほどではなかったです。',
    ],
}
INSIGHT_TEMPLATES = [
    {
        'category': 'sales',
        'severity': 'info',
        'title': '週末の売上が平日比{pct}%増加',
        'message': '直近4週間の週末売上は平日と比較して{pct}%高い傾向があります。週末のスタッフ配置を強化することで更なる売上向上が期待できます。',
    },
    {
        'category': 'customer',
        'severity': 'warning',
        'title': 'リピート率が前月比{pct}%低下',
        'message': 'リピート顧客の割合が前月と比較して{pct}%低下しています。顧客満足度の改善策を検討してください。',
    },
    {
        'category': 'staffing',
        'severity': 'info',
        'title': '{name}さんの予約稼働率が{pct}%',
        'message': '{name}さんの予約枠稼働率が{pct}%と高水準を維持しています。枠数の拡大を検討してください。',
    },
    {
        'category': 'menu',
        'severity': 'info',
        'title': '人気メニュー「{item}」の注文数が増加',
        'message': '直近2週間で「{item}」の注文数が{pct}%増加しています。在庫確保と原価率の確認を推奨します。',
    },
    {
        'category': 'customer',
        'severity': 'critical',
        'title': 'NPS低下: 直近1週間のスコアが{score}',
        'message': '直近1週間のNPSが{score}と低下傾向にあります。低評価のフィードバックを確認し、改善策を実施してください。',
    },
    {
        'category': 'sales',
        'severity': 'warning',
        'title': '平日午前の稼働率が{pct}%と低水準',
        'message': '平日10〜12時の予約稼働率が{pct}%に留まっています。割引キャンペーンやSNS告知で集客を強化しましょう。',
    },
    {
        'category': 'inventory',
        'severity': 'warning',
        'title': '在庫切れリスク: {item}',
        'message': '「{item}」の在庫が残り{count}個です。現在の消費ペースだと{days}日で在庫切れになる見込みです。',
    },
    {
        'category': 'staffing',
        'severity': 'critical',
        'title': '来週{day}のシフト不足',
        'message': '来週{day}のキャスト配置が必要人数に対して{count}名不足しています。早急にシフト調整を行ってください。',
    },
]


class Command(BaseCommand):
    help = 'デモデータ生成（--seed で過去90日分、デフォルトは当日差分のみ）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed', action='store_true',
            help='過去90日分の履歴データを一括生成（既存デモデータを削除してから再生成）',
        )
        parser.add_argument(
            '--days', type=int, default=90,
            help='--seed 時の生成日数（デフォルト: 90）',
        )

    def handle(self, *args, **options):
        if not SiteSettings.load().demo_mode_enabled:
            self.stdout.write('デモモード無効 — スキップ')
            return

        store = Store.objects.first()
        if not store:
            self.stderr.write('Store が存在しません')
            return

        now = timezone.localtime(timezone.now())

        if options['seed']:
            self._clean_demo_data()
            self._seed_historical(store, now, options['days'])

        today = now.date()
        current_hour = now.hour
        self._generate_shifts(store, today, current_hour, now)
        self._generate_orders(store, today, current_hour, now)
        self._generate_schedules(store, today, current_hour, now)
        self._generate_visitor_counts(store, today, current_hour)
        self._generate_attendance(store, today, current_hour, now)
        self._generate_checkins(store, today, now)
        self._generate_feedback(store, today, now)
        self._generate_insights(store, now)

        self.stdout.write(self.style.SUCCESS('デモデータ生成完了'))

    # ==============================
    # シード（過去履歴一括生成）
    # ==============================

    def _clean_demo_data(self):
        """全デモデータを削除"""
        counts = {}
        for model in [
            OrderItem, Order, Schedule, VisitorCount,
            AttendanceStamp, WorkAttendance,
            ShiftAssignment, ShiftPeriod,
            CustomerFeedback, BusinessInsight,
        ]:
            if model == OrderItem:
                c, _ = model.objects.filter(order__is_demo=True).delete()
            else:
                c, _ = model.objects.filter(is_demo=True).delete()
            if c:
                counts[model.__name__] = c
        self.stdout.write(f'  削除: {counts}')

    def _seed_historical(self, store, now, seed_days):
        """過去N日分のデモ履歴データを生成"""
        self.stdout.write(f'過去{seed_days}日分の履歴データを生成中...')

        staffs = list(Staff.objects.filter(store=store))
        cast_staffs = [s for s in staffs if s.staff_type == 'fortune_teller']
        products = list(Product.objects.filter(store=store, is_active=True)[:20])

        for days_ago in range(seed_days, 0, -1):
            day = now.date() - timedelta(days=days_ago)
            day_dt = now.replace(
                year=day.year, month=day.month, day=day.day,
                hour=22, minute=0, second=0, microsecond=0,
            )
            weekday = day.weekday()
            is_weekend = weekday >= 5

            # 日ごとの売上ボリューム（週末は1.3-1.5倍）
            volume_mult = random.uniform(1.3, 1.5) if is_weekend else 1.0
            # 曜日による緩やかなトレンド
            trend_mult = 1.0 + (seed_days - days_ago) / seed_days * 0.15

            self._seed_day_shifts(store, staffs, day, day_dt)
            self._seed_day_orders(
                store, products, day, day_dt, volume_mult, trend_mult,
            )
            self._seed_day_schedules(
                store, cast_staffs, day, day_dt, volume_mult,
            )
            self._seed_day_visitors(store, day, volume_mult)
            self._seed_day_attendance(store, staffs, day, day_dt)

        # フィードバック: 過去全期間に分散
        self._seed_historical_feedback(store, now, seed_days)
        # インサイト: 過去数回分
        self._seed_historical_insights(store, staffs, products, now)

        self.stdout.write(self.style.SUCCESS(
            f'  履歴データ生成完了（{seed_days}日分）'
        ))

    def _seed_day_shifts(self, store, staffs, day, day_dt):
        """1日分のシフトデモデータ"""
        month_start = day.replace(day=1)
        period, _ = ShiftPeriod.objects.get_or_create(
            store=store, year_month=month_start, is_demo=True,
            defaults={'status': 'approved'},
        )
        for staff in staffs:
            if random.random() < 0.12:
                continue
            pat = random.choice(SHIFT_PATTERNS)
            start_h, end_h, color = pat
            ShiftAssignment.objects.create(
                period=period, staff=staff, date=day,
                start_hour=start_h, end_hour=end_h,
                start_time=dt_time(start_h, 0),
                end_time=dt_time(end_h, 0),
                store=store, color=color, note='デモシフト',
                is_demo=True,
            )

    def _seed_day_orders(self, store, products, day, day_dt, vol, trend):
        """1日分の注文デモデータ"""
        if not products:
            return
        for hour in range(10, 22):
            num_orders = max(1, int(random.randint(1, 5) * vol * trend))
            for _ in range(num_orders):
                order_time = day_dt.replace(
                    hour=hour, minute=random.randint(0, 59),
                )
                customer_hash = random.choice(CUSTOMER_HASHES) if random.random() < 0.6 else None
                order = Order.objects.create(
                    store=store, status='CLOSED',
                    payment_status='paid',
                    channel=random.choice(CHANNELS),
                    customer_line_user_hash=customer_hash,
                    is_demo=True,
                )
                Order.objects.filter(pk=order.pk).update(created_at=order_time)
                sample = random.sample(products, min(random.randint(1, 4), len(products)))
                for prod in sample:
                    OrderItem.objects.create(
                        order=order, product=prod,
                        qty=random.randint(1, 3),
                        unit_price=prod.price,
                        status='CLOSED',
                    )

    def _seed_day_schedules(self, store, cast_staffs, day, day_dt, vol):
        """1日分の予約デモデータ（キャンセル含む）"""
        if not cast_staffs:
            return
        for hour in range(10, 21):
            if random.random() < 0.3:
                continue
            num = max(1, int(random.randint(1, 2) * vol))
            for _ in range(num):
                staff = random.choice(cast_staffs)
                start = day_dt.replace(hour=hour, minute=random.choice([0, 30]))
                end = start + timedelta(minutes=random.choice([30, 60]))
                is_cancelled = random.random() < 0.08
                is_checked_in = not is_cancelled and random.random() < 0.75
                Schedule.objects.create(
                    staff=staff, start=start, end=end,
                    customer_name=random.choice(CUSTOMER_NAMES),
                    is_temporary=False,
                    is_cancelled=is_cancelled,
                    is_checked_in=is_checked_in,
                    checked_in_at=start + timedelta(minutes=random.randint(-5, 10)) if is_checked_in else None,
                    price=staff.price,
                    memo='デモ予約',
                    is_demo=True,
                )

    def _seed_day_visitors(self, store, day, vol):
        """1日分の来客数デモデータ"""
        for hour in range(9, 23):
            base = random.randint(5, 25)
            if 12 <= hour <= 14 or 18 <= hour <= 20:
                base = int(base * 1.6)
            base = int(base * vol)
            VisitorCount.objects.update_or_create(
                store=store, date=day, hour=hour,
                defaults={
                    'estimated_visitors': base,
                    'pir_count': base + random.randint(0, 10),
                    'order_count': max(1, base // 3),
                    'is_demo': True,
                },
            )

    def _seed_day_attendance(self, store, staffs, day, day_dt):
        """1日分の勤怠データ（全状態カバー: 退勤済み中心）"""
        for staff in staffs:
            if random.random() < 0.1:
                continue
            clock_in_h = random.randint(9, 11)
            clock_in_m = random.randint(0, 15)
            clock_in_time = day_dt.replace(
                hour=clock_in_h, minute=clock_in_m, second=0, microsecond=0,
            )
            clock_out_h = clock_in_h + random.randint(6, 10)
            if clock_out_h > 22:
                clock_out_h = 22
            clock_out_time = day_dt.replace(
                hour=clock_out_h, minute=random.randint(0, 30),
                second=0, microsecond=0,
            )
            work_minutes = (clock_out_h - clock_in_h) * 60
            overtime = max(0, work_minutes - 480)

            # 打刻レコード
            self._create_stamp(staff, 'clock_in', clock_in_time)
            # 過去データは全員休憩あり+退勤済み
            break_h = clock_in_h + random.randint(3, 5)
            if break_h < clock_out_h:
                break_start = day_dt.replace(hour=break_h, minute=0, second=0, microsecond=0)
                break_end = break_start + timedelta(minutes=random.choice([30, 45, 60]))
                self._create_stamp(staff, 'break_start', break_start)
                self._create_stamp(staff, 'break_end', break_end)
            self._create_stamp(staff, 'clock_out', clock_out_time)

            WorkAttendance.objects.update_or_create(
                staff=staff, date=day,
                defaults={
                    'clock_in': clock_in_time.time(),
                    'clock_out': clock_out_time.time(),
                    'regular_minutes': min(work_minutes, 480),
                    'overtime_minutes': overtime,
                    'break_minutes': random.choice([30, 45, 60]),
                    'source': 'qr',
                    'is_demo': True,
                },
            )

    def _seed_historical_feedback(self, store, now, seed_days):
        """過去N日分のフィードバックデモデータ"""
        created = 0
        for days_ago in range(seed_days, 0, -1):
            day_dt = now - timedelta(days=days_ago)
            num = random.randint(1, 5)
            for _ in range(num):
                # NPS分布: 推奨者45%, 中立30%, 批判者25%
                roll = random.random()
                if roll < 0.45:
                    nps = random.randint(9, 10)
                    sentiment = 'positive'
                elif roll < 0.75:
                    nps = random.randint(7, 8)
                    sentiment = 'neutral'
                else:
                    nps = random.randint(0, 6)
                    sentiment = 'negative'

                comment = random.choice(FEEDBACK_COMMENTS[sentiment])
                fb = CustomerFeedback.objects.create(
                    store=store, nps_score=nps,
                    food_rating=min(5, max(1, nps // 2)),
                    service_rating=min(5, max(1, (nps + 1) // 2)),
                    ambiance_rating=random.randint(3, 5),
                    comment=comment, sentiment=sentiment,
                    customer_hash=random.choice(CUSTOMER_HASHES),
                    is_demo=True,
                )
                fb_time = day_dt.replace(
                    hour=random.randint(10, 21),
                    minute=random.randint(0, 59),
                )
                CustomerFeedback.objects.filter(pk=fb.pk).update(created_at=fb_time)
                created += 1

        self.stdout.write(f'  Feedback: {created}件生成')

    def _seed_historical_insights(self, store, staffs, products, now):
        """過去のインサイトデモデータ"""
        created = 0
        staff_names = [s.name for s in staffs] or ['スタッフA']
        product_names = [p.name for p in products] or ['商品A']
        days_of_week = ['月曜', '火曜', '水曜', '木曜', '金曜', '土曜', '日曜']

        for days_ago in [1, 3, 5, 7, 14, 21, 30, 45, 60]:
            template = random.choice(INSIGHT_TEMPLATES)
            title = template['title'].format(
                pct=random.randint(5, 40),
                name=random.choice(staff_names),
                item=random.choice(product_names),
                score=random.randint(-20, 30),
                day=random.choice(days_of_week),
                count=random.randint(1, 3),
                days=random.randint(3, 10),
            )
            message = template['message'].format(
                pct=random.randint(5, 40),
                name=random.choice(staff_names),
                item=random.choice(product_names),
                score=random.randint(-20, 30),
                day=random.choice(days_of_week),
                count=random.randint(1, 3),
                days=random.randint(3, 10),
            )
            ins = BusinessInsight.objects.create(
                store=store,
                category=template['category'],
                severity=template['severity'],
                title=title,
                message=message,
                is_read=days_ago > 7,
                is_demo=True,
            )
            ins_time = now - timedelta(days=days_ago, hours=random.randint(0, 12))
            BusinessInsight.objects.filter(pk=ins.pk).update(created_at=ins_time)
            created += 1

        self.stdout.write(f'  Insight: {created}件生成')

    # ==============================
    # 当日分（ライブ差分追加）
    # ==============================

    def _generate_shifts(self, store, today, current_hour, now):
        """当日のシフト割当デモデータ"""
        existing = ShiftAssignment.objects.filter(
            date=today, is_demo=True, period__store=store,
        ).count()
        if existing > 0:
            return

        staffs = list(Staff.objects.filter(store=store))
        if not staffs:
            return

        month_start = today.replace(day=1)
        period, _ = ShiftPeriod.objects.get_or_create(
            store=store, year_month=month_start, is_demo=True,
            defaults={'status': 'approved'},
        )

        created = 0
        for staff in staffs:
            if random.random() < 0.15:
                continue
            pat = random.choice(SHIFT_PATTERNS)
            start_h, end_h, color = pat
            ShiftAssignment.objects.create(
                period=period, staff=staff, date=today,
                start_hour=start_h, end_hour=end_h,
                start_time=dt_time(start_h, 0),
                end_time=dt_time(end_h, 0),
                store=store, color=color, note='デモシフト',
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
                store=store, is_demo=True, created_at__date=today,
            ).values_list('created_at__hour', flat=True).distinct()
        )

        created = 0
        for hour in range(10, min(current_hour + 1, 23)):
            if hour in existing_hours:
                continue
            num_orders = random.randint(2, 6)
            for _ in range(num_orders):
                order_time = now.replace(
                    hour=hour, minute=random.randint(0, 59), second=0,
                )
                customer_hash = random.choice(CUSTOMER_HASHES) if random.random() < 0.6 else None
                order = Order.objects.create(
                    store=store, status='CLOSED',
                    payment_status='paid',
                    channel=random.choice(CHANNELS),
                    customer_line_user_hash=customer_hash,
                    is_demo=True,
                )
                Order.objects.filter(pk=order.pk).update(created_at=order_time)
                sample = random.sample(products, min(random.randint(1, 4), len(products)))
                for prod in sample:
                    OrderItem.objects.create(
                        order=order, product=prod,
                        qty=random.randint(1, 2),
                        unit_price=prod.price,
                        status='CLOSED',
                    )
                created += 1

        if created:
            self.stdout.write(f'  Order: {created}件生成')

    def _generate_schedules(self, store, today, current_hour, now):
        """当日の予約デモデータ（キャンセル含む）"""
        staff_list = list(Staff.objects.filter(store=store, staff_type='fortune_teller'))
        if not staff_list:
            return

        existing = Schedule.objects.filter(
            start__date=today, is_demo=True,
        ).count()
        if existing >= 15:
            return

        created = 0
        for hour in range(10, min(current_hour + 2, 23)):
            if random.random() < 0.3:
                continue
            staff = random.choice(staff_list)
            start = now.replace(hour=hour, minute=random.choice([0, 30]), second=0, microsecond=0)
            end = start + timedelta(minutes=random.choice([30, 60]))
            is_cancelled = random.random() < 0.08
            Schedule.objects.create(
                staff=staff, start=start, end=end,
                customer_name=random.choice(CUSTOMER_NAMES),
                is_temporary=False,
                is_cancelled=is_cancelled,
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
            base = random.randint(8, 35)
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
        """当日の出退勤デモデータ — 全状態を確実にカバー"""
        staffs = list(Staff.objects.filter(store=store))
        if not staffs:
            return

        existing = AttendanceStamp.objects.filter(
            staff__store=store, stamped_at__date=today, is_demo=True,
        ).count()
        if existing > 0:
            return

        # 状態を明示的に割り当て
        scenarios = ['working', 'on_break', 'back_from_break', 'left', 'left_overtime', 'late']
        created = 0

        for i, staff in enumerate(staffs):
            scenario = scenarios[i % len(scenarios)]
            clock_in_hour = random.randint(9, 11)

            if clock_in_hour > current_hour:
                continue

            # 遅刻シナリオ: 出勤を20-40分遅れに
            if scenario == 'late':
                clock_in_minute = random.randint(20, 40)
            else:
                clock_in_minute = random.randint(0, 10)

            clock_in_time = now.replace(
                hour=clock_in_hour, minute=clock_in_minute,
                second=0, microsecond=0,
            )

            self._create_stamp(staff, 'clock_in', clock_in_time)

            wa, _ = WorkAttendance.objects.update_or_create(
                staff=staff, date=today,
                defaults={
                    'clock_in': clock_in_time.time(),
                    'source': 'qr',
                    'is_demo': True,
                },
            )

            if scenario == 'working' or scenario == 'late':
                # 出勤中（打刻のみ）
                pass

            elif scenario == 'on_break':
                # 休憩中: clock_in + break_start
                if current_hour >= clock_in_hour + 3:
                    break_h = clock_in_hour + random.randint(3, 4)
                    if break_h <= current_hour:
                        break_time = now.replace(
                            hour=break_h, minute=random.randint(0, 15),
                            second=0, microsecond=0,
                        )
                        self._create_stamp(staff, 'break_start', break_time)

            elif scenario == 'back_from_break':
                # 休憩終了後: clock_in + break_start + break_end
                if current_hour >= clock_in_hour + 4:
                    break_h = clock_in_hour + random.randint(3, 4)
                    if break_h < current_hour:
                        break_start = now.replace(
                            hour=break_h, minute=0, second=0, microsecond=0,
                        )
                        break_end = break_start + timedelta(minutes=random.choice([30, 45]))
                        self._create_stamp(staff, 'break_start', break_start)
                        self._create_stamp(staff, 'break_end', break_end)
                        wa.break_minutes = random.choice([30, 45])
                        wa.save(update_fields=['break_minutes'])

            elif scenario in ('left', 'left_overtime'):
                # 退勤済み
                if current_hour >= clock_in_hour + 6:
                    work_hours = random.randint(6, 9)
                    if scenario == 'left_overtime':
                        work_hours = random.randint(9, 11)
                    clock_out_h = min(clock_in_hour + work_hours, current_hour)
                    if clock_out_h <= clock_in_hour:
                        continue

                    clock_out_time = now.replace(
                        hour=clock_out_h, minute=random.randint(0, 30),
                        second=0, microsecond=0,
                    )
                    # 休憩も追加
                    break_h = clock_in_hour + random.randint(3, 5)
                    if break_h < clock_out_h:
                        break_start = now.replace(
                            hour=break_h, minute=0, second=0, microsecond=0,
                        )
                        break_end = break_start + timedelta(minutes=45)
                        self._create_stamp(staff, 'break_start', break_start)
                        self._create_stamp(staff, 'break_end', break_end)

                    self._create_stamp(staff, 'clock_out', clock_out_time)
                    work_min = (clock_out_h - clock_in_hour) * 60
                    overtime = max(0, work_min - 480)
                    wa.clock_out = clock_out_time.time()
                    wa.regular_minutes = min(work_min, 480)
                    wa.overtime_minutes = overtime
                    wa.break_minutes = 45
                    wa.save(update_fields=[
                        'clock_out', 'regular_minutes',
                        'overtime_minutes', 'break_minutes',
                    ])

            created += 1

        if created:
            self.stdout.write(f'  Attendance: {created}件（全状態カバー）')

    def _generate_checkins(self, store, today, now):
        """当日の予約にチェックイン済みフラグを付与"""
        past_schedules = Schedule.objects.filter(
            start__date=today, start__lte=now,
            is_demo=True, is_checked_in=False, is_cancelled=False,
        )

        updated = 0
        for sched in past_schedules:
            if random.random() < 0.7:
                sched.is_checked_in = True
                sched.checked_in_at = sched.start + timedelta(minutes=random.randint(-5, 10))
                sched.save(update_fields=['is_checked_in', 'checked_in_at'])
                updated += 1
        if updated:
            self.stdout.write(f'  Checkin: {updated}件更新')

    def _generate_feedback(self, store, today, now):
        """当日のフィードバックデモデータ"""
        existing = CustomerFeedback.objects.filter(
            store=store, is_demo=True, created_at__date=today,
        ).count()
        if existing >= 3:
            return

        created = 0
        for _ in range(random.randint(2, 5)):
            roll = random.random()
            if roll < 0.45:
                nps = random.randint(9, 10)
                sentiment = 'positive'
            elif roll < 0.75:
                nps = random.randint(7, 8)
                sentiment = 'neutral'
            else:
                nps = random.randint(0, 6)
                sentiment = 'negative'

            fb = CustomerFeedback.objects.create(
                store=store, nps_score=nps,
                food_rating=min(5, max(1, nps // 2)),
                service_rating=min(5, max(1, (nps + 1) // 2)),
                ambiance_rating=random.randint(3, 5),
                comment=random.choice(FEEDBACK_COMMENTS[sentiment]),
                sentiment=sentiment,
                customer_hash=random.choice(CUSTOMER_HASHES),
                is_demo=True,
            )
            fb_time = now.replace(
                hour=random.randint(10, min(now.hour, 21)),
                minute=random.randint(0, 59),
            )
            CustomerFeedback.objects.filter(pk=fb.pk).update(created_at=fb_time)
            created += 1

        if created:
            self.stdout.write(f'  Feedback: {created}件生成')

    def _generate_insights(self, store, now):
        """インサイト — 既存が3件未満なら追加"""
        existing = BusinessInsight.objects.filter(
            store=store, is_demo=True, is_read=False,
        ).count()
        if existing >= 3:
            return

        staffs = list(Staff.objects.filter(store=store))
        products = list(Product.objects.filter(store=store, is_active=True)[:10])
        staff_names = [s.name for s in staffs] or ['スタッフA']
        product_names = [p.name for p in products] or ['商品A']
        days_of_week = ['月曜', '火曜', '水曜', '木曜', '金曜', '土曜', '日曜']

        templates = random.sample(INSIGHT_TEMPLATES, min(3, len(INSIGHT_TEMPLATES)))
        created = 0
        for tmpl in templates:
            fmt_kwargs = {
                'pct': random.randint(5, 40),
                'name': random.choice(staff_names),
                'item': random.choice(product_names),
                'score': random.randint(-20, 30),
                'day': random.choice(days_of_week),
                'count': random.randint(1, 3),
                'days': random.randint(3, 10),
            }
            BusinessInsight.objects.create(
                store=store,
                category=tmpl['category'],
                severity=tmpl['severity'],
                title=tmpl['title'].format(**fmt_kwargs),
                message=tmpl['message'].format(**fmt_kwargs),
                is_demo=True,
            )
            created += 1

        if created:
            self.stdout.write(f'  Insight: {created}件生成')

    # ==============================
    # ユーティリティ
    # ==============================

    def _create_stamp(self, staff, stamp_type, stamped_at):
        """打刻レコードを作成し、時刻を上書き"""
        stamp = AttendanceStamp.objects.create(
            staff=staff, stamp_type=stamp_type,
            totp_used='', is_demo=True,
        )
        AttendanceStamp.objects.filter(pk=stamp.pk).update(stamped_at=stamped_at)
        return stamp
