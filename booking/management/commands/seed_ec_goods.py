"""占いグッズECデモデータ投入コマンド (20品)"""
import random
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from booking.models import Category, Product, ProductTranslation, Store


EC_SKU_PREFIX = 'EC-'

CATEGORY_PRODUCTS = {
    'タロット＆カード': {
        'color': '#7C3AED',
        'items': [
            ('EC-TAR-001', 'ライダーウェイトタロット', 'ウェイト版の定番タロットデッキ。初心者〜上級者まで', 2800, 15),
            ('EC-TAR-002', 'マルセイユタロット', 'フランス伝統のマルセイユ版22枚大アルカナ', 3200, 12),
            ('EC-TAR-003', 'オラクルカード 天使', '44枚の天使オラクルカード。日本語解説書付', 3800, 8),
            ('EC-TAR-004', 'ルノルマンカード', '36枚のルノルマンカード。実践ガイド付', 2400, 20),
            ('EC-TAR-005', 'タロットクロス（ベルベット）', '高品質ベルベット製タロット展開用クロス 60×60cm', 2600, 10),
        ],
    },
    'パワーストーン': {
        'color': '#8B5CF6',
        'items': [
            ('EC-STN-001', 'アメジスト原石クラスター', '直感力・霊性を高める紫水晶。浄化済み', 4800, 5),
            ('EC-STN-002', 'ローズクォーツ丸玉', '恋愛運UP。直径約4cm天然ローズクォーツ', 3200, 8),
            ('EC-STN-003', '水晶ポイント（天然）', '万能の浄化石。瞑想・ヒーリングに', 2800, 12),
            ('EC-STN-004', 'タイガーアイブレスレット', '金運・仕事運のお守りブレスレット 10mm玉', 3800, 15),
            ('EC-STN-005', 'ラピスラズリペンダント', '幸運の石。シルバー925チェーン付', 8000, 3),
            ('EC-STN-006', 'さざれ石ミックス（浄化用）', '水晶・アメジスト・シトリンMIX 200g', 1800, 25),
        ],
    },
    'お守り＆浄化': {
        'color': '#10B981',
        'items': [
            ('EC-AMU-001', 'ホワイトセージ（バンドル）', 'カリフォルニア産オーガニック浄化セージ', 1200, 30),
            ('EC-AMU-002', 'パロサント スティック3本', '聖なる木。空間浄化＆リラックス効果', 1000, 50),
            ('EC-AMU-003', '浄化スプレー（セージ＆ラベンダー）', '手軽に空間浄化。天然精油100% 100ml', 2200, 18),
            ('EC-AMU-004', 'シンギングボウル（チベット製）', 'チベット仏教の浄化・瞑想用ボウル 直径12cm', 7500, 5),
            ('EC-AMU-005', '盛り塩セット（八角皿付）', '天然粗塩＋八角盛り塩皿2枚セット', 1500, 20),
        ],
    },
    '占い書籍': {
        'color': '#F59E0B',
        'items': [
            ('EC-BK-001', 'はじめてのタロット入門', 'カード意味・スプレッド・実践リーディング', 1800, 18),
            ('EC-BK-002', '西洋占星術 完全ガイド', 'ホロスコープの読み方を基礎から解説', 2200, 10),
            ('EC-BK-003', '手相の教科書', '手相の基本線から応用まで。写真付き解説', 1500, 15),
            ('EC-BK-004', '数秘術であなたの運命を読む', '生年月日から導く運命数・使命数', 1600, 12),
        ],
    },
}


class Command(BaseCommand):
    help = '占いグッズECデモデータを投入します（20品）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='既存のEC-プレフィックスSKU商品を削除してから再作成',
        )

    def handle(self, *args, **options):
        store = Store.objects.first()
        if not store:
            self.stderr.write(self.style.ERROR('Store が見つかりません。先に seed_mock_data を実行してください。'))
            return

        if options['reset']:
            deleted_count, _ = Product.objects.filter(
                store=store, sku__startswith=EC_SKU_PREFIX,
            ).delete()
            self.stdout.write(f'  リセット: {deleted_count} 件削除')

        existing_skus = set(
            Product.objects.filter(store=store, sku__startswith=EC_SKU_PREFIX)
            .values_list('sku', flat=True)
        )

        created = 0
        skipped = 0

        for cat_name, cat_data in CATEGORY_PRODUCTS.items():
            category, _ = Category.objects.get_or_create(
                store=store,
                name=cat_name,
                defaults={
                    'sort_order': Category.objects.filter(store=store).count(),
                    'is_restaurant_menu': False,
                },
            )

            bg_color = cat_data['color']
            for sku, name, desc, price, stock in cat_data['items']:
                if sku in existing_skus:
                    skipped += 1
                    continue

                product = Product.objects.create(
                    store=store,
                    category=category,
                    sku=sku,
                    name=name,
                    description=desc,
                    price=price,
                    stock=stock,
                    low_stock_threshold=max(3, stock // 5),
                    is_active=True,
                    is_ec_visible=True,
                    popularity=random.randint(20, 95),
                    margin_rate=round(random.uniform(0.25, 0.55), 2),
                )
                self._generate_product_image(product, bg_color, cat_name)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'  EC占いグッズ: {created} 件作成, {skipped} 件スキップ（既存）'
        ))

    def _generate_product_image(self, product, bg_color, category_name):
        """Pillow でカテゴリ別の背景色 + 商品名テキストのプレースホルダー画像を生成"""
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return

        width, height = 400, 300
        hex_color = bg_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)

        img = Image.new('RGB', (width, height), (r, g, b))
        draw = ImageDraw.Draw(img)

        font_large = None
        font_small = None
        try:
            font_large = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 24)
            font_small = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc', 16)
        except (OSError, IOError):
            try:
                font_large = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 24)
                font_small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
            except (OSError, IOError):
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

        cat_bbox = draw.textbbox((0, 0), category_name, font=font_small)
        cat_w = cat_bbox[2] - cat_bbox[0]
        draw.text(((width - cat_w) / 2, 30), category_name, fill=(255, 255, 255, 200), font=font_small)

        name = product.name
        if len(name) > 10:
            mid = len(name) // 2
            lines = [name[:mid], name[mid:]]
        else:
            lines = [name]

        y_offset = (height - len(lines) * 35) / 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_large)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) / 2, y_offset), line, fill='#FFFFFF', font=font_large)
            y_offset += 35

        price_text = f'¥{product.price:,}'
        price_bbox = draw.textbbox((0, 0), price_text, font=font_small)
        price_w = price_bbox[2] - price_bbox[0]
        draw.text(((width - price_w) / 2, height - 50), price_text, fill=(255, 255, 255, 200), font=font_small)

        buf = BytesIO()
        img.save(buf, format='PNG')
        filename = f'{product.sku.lower()}.png'
        product.image.save(filename, ContentFile(buf.getvalue()), save=True)
