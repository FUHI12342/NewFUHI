"""飲食系デモデータ（シーシャ・ドリンク・フード）を削除するコマンド"""
from django.core.management.base import BaseCommand

from booking.models import Category, Order, OrderItem, Product, StockMovement


FOOD_DRINK_CATEGORIES = ('シーシャ', 'ドリンク', 'フード')


class Command(BaseCommand):
    help = '飲食系デモデータ（シーシャ・ドリンク・フード）を関連データごと削除します'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='削除せずに対象件数のみ表示',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        products = Product.objects.filter(sku__regex=r'^(SH|DR|FD)-')
        product_ids = list(products.values_list('id', flat=True))

        # 関連データのカウント
        order_items = OrderItem.objects.filter(product_id__in=product_ids)
        stock_movements = StockMovement.objects.filter(product_id__in=product_ids)
        # 飲食商品のみで構成される注文（全OrderItemが飲食系の注文）
        orders_with_food = Order.objects.filter(items__product_id__in=product_ids).distinct()
        categories = Category.objects.filter(name__in=FOOD_DRINK_CATEGORIES)

        self.stdout.write(f'対象:')
        self.stdout.write(f'  商品: {products.count()} 件')
        self.stdout.write(f'  注文明細: {order_items.count()} 件')
        self.stdout.write(f'  在庫移動: {stock_movements.count()} 件')
        self.stdout.write(f'  関連注文: {orders_with_food.count()} 件')
        self.stdout.write(f'  カテゴリ: {categories.count()} 件')

        if dry_run:
            self.stdout.write('[DRY RUN] 削除は実行しません')
            return

        # 削除順: OrderItem → StockMovement → Product → 空Category → 空Order
        del_oi, _ = order_items.delete()
        self.stdout.write(f'  注文明細削除: {del_oi}')

        del_sm, _ = stock_movements.delete()
        self.stdout.write(f'  在庫移動削除: {del_sm}')

        del_p, _ = products.delete()
        self.stdout.write(f'  商品削除: {del_p}')

        del_cat = 0
        for cat in categories:
            if cat.products.count() == 0:
                cat.delete()
                del_cat += 1
        self.stdout.write(f'  カテゴリ削除: {del_cat}')

        # 明細が0件になった注文を削除
        del_orders = 0
        for order in orders_with_food:
            if order.items.count() == 0:
                order.delete()
                del_orders += 1
        self.stdout.write(f'  空注文削除: {del_orders}')

        self.stdout.write(self.style.SUCCESS('飲食系データ削除完了'))
