"""飲食物＆シーシャ メニューデモデータ投入コマンド"""
import random

from django.core.management.base import BaseCommand

from booking.models import Category, Product, Store


FOOD_SKU_PREFIXES = ('SH-', 'DR-', 'FD-')

CATEGORY_PRODUCTS = {
    'ドリンク': {
        'sort': 0,
        'items': [
            ('DR-001', 'ブレンドコーヒー', 'オリジナルブレンド。ホット / アイス選択可', 500, 99),
            ('DR-002', 'カフェラテ', 'エスプレッソ＋スチームミルク', 600, 99),
            ('DR-003', 'ほうじ茶ラテ', '香ばしいほうじ茶のラテ', 600, 99),
            ('DR-004', '抹茶ラテ', '京都産抹茶使用。ホット / アイス', 650, 99),
            ('DR-005', 'ジンジャーエール', '自家製ジンジャーシロップ使用', 550, 99),
            ('DR-006', 'オレンジジュース', '100%ストレートジュース', 500, 99),
            ('DR-007', 'チャイティー', 'スパイス香るマサラチャイ', 600, 99),
            ('DR-008', 'ハーブティー（カモミール）', 'リラックス効果のカモミール', 550, 99),
            ('DR-009', 'ビール（生）', 'プレミアムモルツ 350ml', 700, 99),
            ('DR-010', 'レモンサワー', '生搾りレモンサワー', 600, 99),
            ('DR-011', 'カシスオレンジ', 'カシスリキュール＋100%OJ', 650, 99),
            ('DR-012', 'ハイボール', 'サントリー角ハイボール', 600, 99),
        ],
    },
    'フード': {
        'sort': 1,
        'items': [
            ('FD-001', 'ナポリタン', '昔ながらの喫茶店ナポリタン', 900, 50),
            ('FD-002', 'カルボナーラ', '濃厚チーズ＆ベーコン', 1000, 50),
            ('FD-003', 'チーズトースト', 'とろけるチーズのトースト', 500, 50),
            ('FD-004', 'BLTサンドイッチ', 'ベーコン・レタス・トマトのサンド', 700, 50),
            ('FD-005', 'フライドポテト', 'カリカリフライドポテト。ケチャップ付', 500, 80),
            ('FD-006', 'ミックスナッツ', 'アーモンド・カシュー・マカダミア', 400, 80),
            ('FD-007', 'チョコレートケーキ', '濃厚ガトーショコラ', 600, 30),
            ('FD-008', 'チーズケーキ', 'NYスタイル ベイクドチーズケーキ', 600, 30),
            ('FD-009', 'アサイーボウル', 'アサイー＋グラノーラ＋フルーツ', 800, 30),
            ('FD-010', '枝豆', '塩茹で枝豆', 350, 80),
        ],
    },
    'シーシャ': {
        'sort': 2,
        'items': [
            ('SH-001', 'ダブルアップル', '定番人気No.1。甘くスパイシーなアニス風味', 1500, 99),
            ('SH-002', 'ブルーベリーミント', 'ブルーベリー＋ミントの爽やかブレンド', 1500, 99),
            ('SH-003', 'グレープミント', 'ジューシーなグレープ＋ミント', 1500, 99),
            ('SH-004', 'ピーチ', '甘い桃のフレーバー。女性人気No.1', 1500, 99),
            ('SH-005', 'レモンミント', 'レモン＋スペアミント。さっぱり系', 1500, 99),
            ('SH-006', 'ストロベリー', '甘酸っぱいイチゴ。マイルドな煙', 1500, 99),
            ('SH-007', 'マンゴー', 'トロピカルマンゴー。濃厚な甘み', 1500, 99),
            ('SH-008', 'スイカミント', '夏限定人気フレーバー。爽快感抜群', 1500, 99),
            ('SH-009', 'チャイスパイス', 'シナモン＋カルダモン＋クローブ', 1600, 99),
            ('SH-010', 'ローズ', '華やかなバラの香り。リラックスタイムに', 1600, 99),
            ('SH-011', 'チョコミント', 'デザート感覚。チョコ＋ミント', 1600, 99),
            ('SH-012', 'カスタムMIX', 'お好きなフレーバー2種MIX', 1800, 99),
        ],
    },
}


class Command(BaseCommand):
    help = '飲食物・シーシャ メニューのデモデータを投入します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='既存の飲食系SKU商品を削除してから再作成',
        )

    def handle(self, *args, **options):
        store = Store.objects.first()
        if not store:
            self.stderr.write(self.style.ERROR(
                'Store が見つかりません。先に seed_mock_data を実行してください。'
            ))
            return

        if options['reset']:
            from django.db.models import Q
            q = Q()
            for prefix in FOOD_SKU_PREFIXES:
                q |= Q(sku__startswith=prefix)
            deleted_count, _ = Product.objects.filter(q, store=store).delete()
            self.stdout.write(f'  リセット: {deleted_count} 件削除')

        existing_skus = set(
            Product.objects.filter(store=store).values_list('sku', flat=True)
        )

        created = 0
        skipped = 0

        for cat_name, cat_data in CATEGORY_PRODUCTS.items():
            category, _ = Category.objects.get_or_create(
                store=store,
                name=cat_name,
                defaults={
                    'sort_order': cat_data['sort'],
                    'is_restaurant_menu': True,
                },
            )
            # 既存カテゴリでも is_restaurant_menu を確実に True にする
            if not category.is_restaurant_menu:
                category.is_restaurant_menu = True
                category.save(update_fields=['is_restaurant_menu'])

            for sku, name, desc, price, stock in cat_data['items']:
                if sku in existing_skus:
                    skipped += 1
                    continue

                Product.objects.create(
                    store=store,
                    category=category,
                    sku=sku,
                    name=name,
                    description=desc,
                    price=price,
                    stock=stock,
                    low_stock_threshold=max(3, stock // 5),
                    is_active=True,
                    is_ec_visible=False,  # 店内メニューのみ（EC非公開）
                    popularity=random.randint(30, 95),
                    margin_rate=round(random.uniform(0.40, 0.70), 2),
                )
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'飲食メニュー: {created} 件作成, {skipped} 件スキップ（既存）'
        ))
