"""POS画面・決済API"""
import json
import logging
from datetime import datetime

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext as _
from django.template.loader import render_to_string

from booking.views_restaurant_dashboard import AdminSidebarMixin
from booking.models import (
    Store, Staff, Product, Category, Order, OrderItem,
    PaymentMethod, POSTransaction, TableSeat,
    StockMovement, apply_stock_movement,
    TaxServiceCharge,
)

logger = logging.getLogger(__name__)


def _get_user_store(request):
    if request.user.is_superuser:
        store_id = request.GET.get('store_id') or request.POST.get('store_id')
        if store_id:
            return Store.objects.filter(id=store_id).first()
        return Store.objects.first()
    try:
        return request.user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


def _generate_receipt_number():
    """レシート番号生成"""
    now = timezone.now()
    import random
    return f"R{now.strftime('%y%m%d%H%M')}{random.randint(100, 999)}"


class POSView(AdminSidebarMixin, TemplateView):
    """フルスクリーンPOS画面"""
    template_name = 'admin/booking/pos.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)

        categories = Category.objects.filter(store=store) if store else []
        products = Product.objects.filter(store=store, is_active=True).select_related('category') if store else []
        tables = TableSeat.objects.filter(store=store, is_active=True) if store else []
        payment_methods = PaymentMethod.objects.filter(store=store, is_enabled=True) if store else []

        open_orders = Order.objects.filter(
            store=store, status=Order.STATUS_OPEN,
        ).prefetch_related('items__product') if store else []

        ctx.update({
            'title': _('POS'),
            'has_permission': True,
            'store': store,
            'categories': categories,
            'products': products,
            'tables': tables,
            'payment_methods': payment_methods,
            'open_orders': open_orders,
        })
        return ctx


class POSOrderAPIView(LoginRequiredMixin, View):
    """注文一覧・作成"""

    def get(self, request):
        store = _get_user_store(request)
        status = request.GET.get('status', 'OPEN')
        orders = Order.objects.filter(
            store=store, status=status,
        ).prefetch_related('items__product').order_by('-created_at') if store else []

        data = []
        for order in orders:
            items = [{
                'id': item.id,
                'product_name': item.product.name,
                'qty': item.qty,
                'unit_price': item.unit_price,
                'subtotal': item.qty * item.unit_price,
                'status': item.status,
            } for item in order.items.all()]

            total = sum(i['subtotal'] for i in items)
            data.append({
                'id': order.id,
                'table_label': order.table_label,
                'status': order.status,
                'payment_status': order.payment_status,
                'items': items,
                'total': total,
                'created_at': order.created_at.isoformat(),
            })
        return JsonResponse(data, safe=False)

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        store = _get_user_store(request)
        table_label = data.get('table_label', '')
        table_seat_id = data.get('table_seat_id')

        order = Order.objects.create(
            store=store,
            table_label=table_label,
            table_seat_id=table_seat_id,
            status=Order.STATUS_OPEN,
            channel='pos',
        )
        return JsonResponse({'id': order.id, 'table_label': order.table_label}, status=201)


class POSOrderItemAPIView(LoginRequiredMixin, View):
    """注文商品追加・更新・削除"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        order = get_object_or_404(Order, pk=data.get('order_id'))
        product = get_object_or_404(Product, pk=data.get('product_id'))

        # 既存アイテムがあればqty追加
        existing = OrderItem.objects.filter(
            order=order, product=product, status=OrderItem.STATUS_ORDERED,
        ).first()
        if existing:
            existing.qty += data.get('qty', 1)
            existing.save(update_fields=['qty'])
            item = existing
        else:
            item = OrderItem.objects.create(
                order=order,
                product=product,
                qty=data.get('qty', 1),
                unit_price=product.price,
            )

        return JsonResponse({
            'id': item.id,
            'product_name': product.name,
            'qty': item.qty,
            'unit_price': item.unit_price,
        }, status=201)

    def put(self, request, pk=None):
        item = get_object_or_404(OrderItem, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        if 'qty' in data:
            item.qty = max(1, int(data['qty']))
        if 'status' in data:
            item.status = data['status']
        item.save()
        return JsonResponse({'id': item.id, 'qty': item.qty, 'status': item.status})

    def delete(self, request, pk=None):
        item = get_object_or_404(OrderItem, pk=pk)
        item.delete()
        return HttpResponse('', status=204)


class POSCheckoutAPIView(LoginRequiredMixin, View):
    """決済処理"""

    def post(self, request):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        order = get_object_or_404(Order, pk=data.get('order_id'))
        payment_method_id = data.get('payment_method_id')
        cash_received = data.get('cash_received')

        with transaction.atomic():
            # 注文を排他ロック
            order = Order.objects.select_for_update().get(pk=order.pk)

            items = order.items.select_related('product').all()
            subtotal = sum(item.qty * item.unit_price for item in items)

            # 動的税率計算: TaxServiceCharge から有効な税・サービス料を取得
            now_hour = timezone.now().hour
            charges = TaxServiceCharge.objects.filter(
                store=order.store, is_active=True,
            )
            tax = 0
            for charge in charges:
                if charge.applies_after_hour is not None and now_hour < charge.applies_after_hour:
                    continue
                tax += int(subtotal * charge.rate / 100)

            discount = order.discount_amount
            total = subtotal + tax - discount

            # POSTransaction作成
            receipt_number = _generate_receipt_number()
            staff = None
            try:
                staff = request.user.staff
            except (Staff.DoesNotExist, AttributeError):
                pass

            change = None
            if cash_received is not None:
                change = int(cash_received) - total

            payment_method = None
            if payment_method_id:
                payment_method = PaymentMethod.objects.filter(pk=payment_method_id).first()

            tx = POSTransaction.objects.create(
                order=order,
                payment_method=payment_method,
                total_amount=total,
                tax_amount=tax,
                discount_amount=discount,
                cash_received=int(cash_received) if cash_received else None,
                change_given=change,
                receipt_number=receipt_number,
                staff=staff,
                completed_at=timezone.now(),
            )

            # 注文ステータス更新
            order.status = Order.STATUS_CLOSED
            order.payment_status = 'paid'
            order.tax_amount = tax
            order.save(update_fields=['status', 'payment_status', 'tax_amount'])

            # 在庫連動（商品を排他ロックして更新）
            for item in items:
                try:
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    StockMovement.objects.create(
                        store=order.store,
                        product=product,
                        movement_type=StockMovement.TYPE_OUT,
                        qty=item.qty,
                        by_staff=staff,
                        note=f'POS決済 #{receipt_number}',
                    )
                    apply_stock_movement(product, StockMovement.TYPE_OUT, item.qty)
                except ValueError:
                    pass  # 在庫不足でもPOS決済は通す

                item.status = OrderItem.STATUS_CLOSED
                item.save(update_fields=['status'])

        return JsonResponse({
            'receipt_number': receipt_number,
            'total': total,
            'tax': tax,
            'change': change,
            'transaction_id': tx.id,
        })


class KitchenDisplayView(AdminSidebarMixin, TemplateView):
    """キッチンディスプレイ"""
    template_name = 'admin/booking/kitchen_display.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_user_store(self.request)
        today = timezone.now().date()

        open_orders = Order.objects.filter(
            store=store, status=Order.STATUS_OPEN,
        ).select_related('table_seat').prefetch_related('items__product').order_by('created_at') if store else []

        # 本日の完了済み注文（新しい順）
        closed_orders = Order.objects.filter(
            store=store, status=Order.STATUS_CLOSED,
            updated_at__date=today,
        ).select_related('table_seat').prefetch_related('items__product').order_by('-updated_at')[:30] if store else []

        ctx.update({
            'title': _('キッチンディスプレイ'),
            'has_permission': True,
            'store': store,
            'open_orders': open_orders,
            'closed_orders': closed_orders,
        })
        return ctx


class KitchenOrdersHTMLView(View):
    """キッチンディスプレイ用 HTML フラグメント（HTMX auto-refresh 向け）"""

    def get(self, request):
        store = _get_user_store(request)
        today = timezone.now().date()

        open_orders = Order.objects.filter(
            store=store, status=Order.STATUS_OPEN,
        ).select_related('table_seat').prefetch_related('items__product').order_by('created_at') if store else []

        closed_orders = Order.objects.filter(
            store=store, status=Order.STATUS_CLOSED,
            updated_at__date=today,
        ).select_related('table_seat').prefetch_related('items__product').order_by('-updated_at')[:30] if store else []

        html = render_to_string(
            'admin/booking/_kitchen_orders_fragment.html',
            {
                'open_orders': open_orders,
                'closed_orders': closed_orders,
                'csrf_token': request.META.get('CSRF_COOKIE', ''),
            },
            request=request,
        )
        return HttpResponse(html)


class KitchenOrderStatusAPI(LoginRequiredMixin, View):
    """OrderItemステータス更新"""

    def put(self, request, pk=None):
        item = get_object_or_404(OrderItem, pk=pk)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        new_status = data.get('status')
        if new_status in [s[0] for s in OrderItem.STATUS_CHOICES]:
            item.status = new_status
            item.save(update_fields=['status'])
            return JsonResponse({'id': item.id, 'status': item.status})
        return JsonResponse({'error': 'Invalid status'}, status=400)


class KitchenOrderCompleteAPI(LoginRequiredMixin, View):
    """注文を完了済みにする（全アイテム配膳済み後）"""

    def post(self, request, pk=None):
        order = get_object_or_404(Order, pk=pk)
        order.status = Order.STATUS_CLOSED
        order.save(update_fields=['status'])
        return JsonResponse({
            'id': order.id,
            'status': order.status,
        })
