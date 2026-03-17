"""飲食系デモデータ（シーシャ・ドリンク・フード）を削除するコマンド"""
from django.core.management.base import BaseCommand

from booking.models import Category, Product


# seed_mock_data で作成された飲食系SKUプレフィックス
FOOD_DRINK_SKU_PREFIXES = ('SH-', 'DR-', 'FD-')
FOOD_DRINK_CATEGORIES = ('シーシャ', 'ドリンク', 'フード')


class Command(BaseCommand):
    help = '飲食系デモデータ（シーシャ・ドリンク・フード）を削除します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='削除せずに対象件数のみ表示',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # 飲食系商品
        products = Product.objects.filter(sku__regex=r'^(SH|DR|FD)-')
        product_count = products.count()

        # 飲食系カテゴリ（商品が0件になるもののみ）
        categories = Category.objects.filter(name__in=FOOD_DRINK_CATEGORIES)
        cat_count = categories.count()

        if dry_run:
            self.stdout.write(f'[DRY RUN] 削除対象:')
            self.stdout.write(f'  商品: {product_count} 件')
            for p in products:
                self.stdout.write(f'    {p.sku} - {p.name}')
            self.stdout.write(f'  カテゴリ: {cat_count} 件')
            for c in categories:
                self.stdout.write(f'    {c.name}')
            return

        deleted_products, _ = products.delete()
        self.stdout.write(f'  商品削除: {deleted_products} 件')

        # カテゴリは商品が残っていなければ削除
        deleted_cats = 0
        for cat in categories:
            if cat.products.count() == 0:
                cat.delete()
                deleted_cats += 1

        self.stdout.write(self.style.SUCCESS(
            f'  飲食系データ削除完了: 商品 {deleted_products} 件, カテゴリ {deleted_cats} 件'
        ))
