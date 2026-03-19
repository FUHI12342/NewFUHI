"""Table order views: TableMenuView, TableCartView, TableOrderView,
TableOrderHistoryView, TableCheckoutView, and table order APIs."""
import json
import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

import requests as http_requests

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import (
    Product, Category, Order, OrderItem, StockMovement,
    TableSeat, PaymentMethod,
)

logger = logging.getLogger(__name__)


def _get_table_cart_key(table_id):
    return f'table_cart_{table_id}'


def _get_table_orders_key(table_id):
    return f'table_orders_{table_id}'


def _get_table_context(request, table_id):
    """共通テーブル注文コンテキスト"""
    seat = get_object_or_404(TableSeat, pk=table_id, is_active=True)
    store = seat.store
    cart = request.session.get(_get_table_cart_key(table_id), {})
    cart_count = sum(item.get('qty', 0) for item in cart.values())
    return {
        'seat': seat,
        'store': store,
        'cart_count': cart_count,
        'table_id': table_id,
    }


class TableMenuView(View):
    """テーブル注文メニュー表示"""
    def get(self, request, table_id):
        ctx = _get_table_context(request, table_id)
        store = ctx['store']

        products_qs = Product.objects.filter(
            store=store, is_active=True,
            category__is_restaurant_menu=True,
        ).select_related('category').order_by('category__sort_order', 'name')

        category_id = request.GET.get('category')
        if category_id:
            products_qs = products_qs.filter(category_id=category_id)

        categories = Category.objects.filter(
            products__store=store, products__is_active=True,
            is_restaurant_menu=True,
        ).distinct().order_by('sort_order', 'name')

        products = []
        for p in products_qs:
            products.append({
                'id': p.id,
                'name': p.name,
                'sku': p.sku or '',
                'description': p.description,
                'price': p.price,
                'image_url': p.image.url if p.image else None,
                'is_sold_out': p.is_sold_out,
                'category_id': p.category_id,
            })

        ctx.update({
            'products': products,
            'categories': categories,
            'current_category': category_id,
            'active_tab': 'menu',
            'cart_add_url': reverse('booking_api:table_cart_add', kwargs={'table_id': table_id}),
        })
        return render(request, 'booking/table_menu.html', ctx)


class TableCartView(View):
    """テーブル注文カート表示"""
    def get(self, request, table_id):
        ctx = _get_table_context(request, table_id)
        cart = request.session.get(_get_table_cart_key(table_id), {})

        cart_items = []
        total = 0
        for product_id, item in cart.items():
            subtotal = item['price'] * item['qty']
            cart_items.append({
                'product_id': product_id,
                'name': item['name'],
                'price': item['price'],
                'qty': item['qty'],
                'subtotal': subtotal,
            })
            total += subtotal

        ctx.update({
            'cart_items': cart_items,
            'total': total,
            'active_tab': 'cart',
            'cart_update_url': reverse('booking_api:table_cart_update', kwargs={'table_id': table_id}),
            'cart_remove_url': reverse('booking_api:table_cart_remove', kwargs={'table_id': table_id}),
        })
        return render(request, 'booking/table_cart.html', ctx)


class TableOrderView(View):
    """テーブル注文確定 (POST)"""
    def post(self, request, table_id):
        seat = get_object_or_404(TableSeat, pk=table_id, is_active=True)
        store = seat.store
        cart_key = _get_table_cart_key(table_id)
        cart = request.session.get(cart_key, {})

        if not cart:
            return redirect('table:table_menu', table_id=table_id)

        normalized = {}
        for pid, item in cart.items():
            try:
                qty = int(item.get('qty', 0))
            except (ValueError, TypeError):
                qty = 0
            if qty > 0:
                normalized[int(pid)] = qty

        if not normalized:
            return redirect('table:table_cart', table_id=table_id)

        product_ids = sorted(normalized.keys())

        with transaction.atomic():
            order = Order.objects.create(
                store=store,
                table_seat=seat,
                table_label=seat.label,
                status=Order.STATUS_OPEN,
                channel='table',
            )

            locked_products = list(
                Product.objects.select_for_update()
                .filter(store=store, is_active=True, id__in=product_ids)
                .order_by("id")
            )
            product_map = {p.id: p for p in locked_products}

            for pid in product_ids:
                p = product_map.get(pid)
                if not p:
                    continue
                qty = normalized[pid]

                if int(p.stock) - int(qty) < 0:
                    messages.error(request, f'{p.name} の在庫が不足しています。')
                    return redirect('table:table_cart', table_id=table_id)

                StockMovement.objects.create(
                    store=store,
                    product=p,
                    movement_type=StockMovement.TYPE_OUT,
                    qty=qty,
                    note=f'table order#{order.id} seat:{seat.label}',
                )
                Product.objects.filter(pk=p.pk).update(stock=F('stock') - abs(int(qty)))
                p.refresh_from_db(fields=['stock'])

                OrderItem.objects.create(
                    order=order,
                    product=p,
                    qty=qty,
                    unit_price=p.price,
                    status=OrderItem.STATUS_ORDERED,
                )

        orders_key = _get_table_orders_key(table_id)
        order_ids = request.session.get(orders_key, [])
        order_ids.append(order.id)
        request.session[orders_key] = order_ids

        request.session[cart_key] = {}

        return redirect('table:table_history', table_id=table_id)


class TableOrderHistoryView(View):
    """テーブル注文履歴表示"""
    def get(self, request, table_id):
        ctx = _get_table_context(request, table_id)
        orders_key = _get_table_orders_key(table_id)
        order_ids = request.session.get(orders_key, [])

        orders = Order.objects.filter(
            id__in=order_ids
        ).prefetch_related('items__product').order_by('-created_at')

        grand_total = 0
        order_list = []
        for order in orders:
            order_total = 0
            for item in order.items.all():
                item.subtotal = item.unit_price * item.qty
                order_total += item.subtotal
            order.order_total = order_total
            grand_total += order_total
            order_list.append(order)

        ctx.update({
            'orders': order_list,
            'grand_total': grand_total,
            'active_tab': 'history',
        })
        return render(request, 'booking/table_order_history.html', ctx)


class TableCheckoutView(View):
    """テーブル注文決済画面"""
    def get(self, request, table_id):
        ctx = _get_table_context(request, table_id)
        store = ctx['store']
        orders_key = _get_table_orders_key(table_id)
        order_ids = request.session.get(orders_key, [])

        orders = Order.objects.filter(
            id__in=order_ids
        ).prefetch_related('items__product').order_by('-created_at')

        grand_total = 0
        for order in orders:
            for item in order.items.all():
                item.subtotal = item.unit_price * item.qty
                grand_total += item.subtotal

        payment_methods = PaymentMethod.objects.filter(
            store=store, is_enabled=True,
        ).order_by('sort_order')

        ctx.update({
            'orders': orders,
            'grand_total': grand_total,
            'payment_methods': payment_methods,
            'active_tab': 'checkout',
        })
        return render(request, 'booking/table_checkout.html', ctx)

    def post(self, request, table_id):
        seat = get_object_or_404(TableSeat, pk=table_id, is_active=True)
        store = seat.store
        payment_method_id = request.POST.get('payment_method_id')

        if not payment_method_id:
            return redirect('table:table_checkout', table_id=table_id)

        method = get_object_or_404(PaymentMethod, pk=payment_method_id, store=store, is_enabled=True)

        orders_key = _get_table_orders_key(table_id)
        order_ids = request.session.get(orders_key, [])

        orders = Order.objects.filter(id__in=order_ids)
        grand_total = 0
        for order in orders:
            for item in order.items.all():
                grand_total += item.unit_price * item.qty

        ctx = _get_table_context(request, table_id)

        if method.method_type == 'cash':
            orders.update(status=Order.STATUS_CLOSED)
            ctx.update({
                'payment_type': 'cash',
                'payment_display': method.display_name,
                'grand_total': grand_total,
            })
        elif method.method_type == 'coiney':
            payment_api_url = method.api_endpoint or settings.PAYMENT_API_URL
            api_key = method.api_key or settings.PAYMENT_API_KEY
            headers = {
                'Authorization': 'Bearer ' + api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-CoineyPayge-Version': '2016-10-25',
            }
            webhook_url = f"{settings.WEBHOOK_URL_BASE}table_{table_id}/"
            data = {
                "amount": grand_total,
                "currency": "jpy",
                "locale": "ja_JP",
                "cancelUrl": request.build_absolute_uri(
                    reverse('table:table_checkout', kwargs={'table_id': table_id})
                ),
                "webhookUrl": webhook_url,
                "method": "creditcard",
                "subject": f"テーブル注文 ({seat.label})",
                "description": f"テーブル {seat.label} お会計",
                "metadata": {"table_id": str(table_id), "order_ids": order_ids},
            }

            try:
                response = http_requests.post(payment_api_url, headers=headers, data=json.dumps(data))
                if response.status_code == 201:
                    payment_url = response.json().get('links', {}).get('paymentUrl')
                    if payment_url:
                        return redirect(payment_url)
            except Exception as e:
                logger.error("Coiney API error for table order: %s", e)

            ctx.update({
                'payment_type': 'other',
                'payment_display': method.display_name,
                'grand_total': grand_total,
            })
        else:
            ctx.update({
                'payment_type': 'other',
                'payment_display': method.display_name,
                'grand_total': grand_total,
            })

        return render(request, 'booking/table_checkout_complete.html', ctx)


# ===== テーブル注文 API =====

class TableCartAddAPI(APIView):
    """テーブル注文カートに商品追加"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, table_id):
        seat = get_object_or_404(TableSeat, pk=table_id, is_active=True)
        product_id = str(request.data.get('product_id', ''))
        try:
            qty = int(request.data.get('qty', 1))
        except (ValueError, TypeError):
            qty = 1

        try:
            product = Product.objects.get(pk=product_id, store=seat.store, is_active=True)
        except Product.DoesNotExist:
            return Response({'status': 'error', 'message': '商品が見つかりません'}, status=404)

        if product.stock < qty:
            return Response({'status': 'error', 'message': '在庫が不足しています'}, status=400)

        cart_key = _get_table_cart_key(table_id)
        cart = request.session.get(cart_key, {})
        if product_id in cart:
            cart[product_id]['qty'] += qty
        else:
            cart[product_id] = {
                'name': product.name,
                'price': product.price,
                'qty': qty,
            }
        request.session[cart_key] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class TableCartUpdateAPI(APIView):
    """テーブル注文カート数量変更"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, table_id):
        get_object_or_404(TableSeat, pk=table_id, is_active=True)
        product_id = str(request.data.get('product_id', ''))
        try:
            qty = int(request.data.get('qty', 0))
        except (ValueError, TypeError):
            qty = 0

        cart_key = _get_table_cart_key(table_id)
        cart = request.session.get(cart_key, {})
        if product_id not in cart:
            return Response({'status': 'error', 'message': 'カートにない商品です'}, status=404)

        if qty <= 0:
            del cart[product_id]
        else:
            cart[product_id]['qty'] = qty
        request.session[cart_key] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class TableCartRemoveAPI(APIView):
    """テーブル注文カートから削除"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, table_id):
        get_object_or_404(TableSeat, pk=table_id, is_active=True)
        product_id = str(request.data.get('product_id', ''))

        cart_key = _get_table_cart_key(table_id)
        cart = request.session.get(cart_key, {})
        if product_id in cart:
            del cart[product_id]
        request.session[cart_key] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class TableOrderCreateAPI(APIView):
    """テーブル注文作成API (在庫ロック)"""
    authentication_classes = []
    permission_classes = []

    def post(self, request, table_id):
        seat = get_object_or_404(TableSeat, pk=table_id, is_active=True)
        store = seat.store
        items = request.data.get('items', [])

        if not items or len(items) > 50:
            return Response({"detail": "items must be 1-50"}, status=status.HTTP_400_BAD_REQUEST)

        normalized = {}
        for it in items:
            pid = it.get("product_id")
            try:
                qty = int(it.get("qty", 1))
            except (TypeError, ValueError):
                qty = 0
            if not pid or qty <= 0:
                continue
            normalized[pid] = normalized.get(pid, 0) + qty

        if not normalized:
            return Response({"detail": "items are invalid"}, status=status.HTTP_400_BAD_REQUEST)

        product_ids = sorted(normalized.keys())

        with transaction.atomic():
            order = Order.objects.create(
                store=store,
                table_seat=seat,
                table_label=seat.label,
                status=Order.STATUS_OPEN,
                channel='table',
            )

            locked_products = list(
                Product.objects.select_for_update()
                .filter(store=store, is_active=True, id__in=product_ids)
                .order_by("id")
            )
            product_map = {p.id: p for p in locked_products}

            missing = [pid for pid in product_ids if pid not in product_map]
            if missing:
                return Response({"detail": f"product not found: {missing}"}, status=status.HTTP_404_NOT_FOUND)

            for pid in product_ids:
                p = product_map[pid]
                qty = normalized[pid]
                if int(p.stock) - int(qty) < 0:
                    return Response({"detail": f"insufficient stock: {p.sku}"}, status=status.HTTP_409_CONFLICT)

            for pid in product_ids:
                p = product_map[pid]
                qty = normalized[pid]

                StockMovement.objects.create(
                    store=store,
                    product=p,
                    movement_type=StockMovement.TYPE_OUT,
                    qty=qty,
                    note=f'table order#{order.id} seat:{seat.label}',
                )
                Product.objects.filter(pk=p.pk).update(stock=F('stock') - abs(int(qty)))
                p.refresh_from_db(fields=['stock'])

                OrderItem.objects.create(
                    order=order,
                    product=p,
                    qty=qty,
                    unit_price=p.price,
                    status=OrderItem.STATUS_ORDERED,
                )

        return Response({"order_id": order.id}, status=status.HTTP_201_CREATED)


class TableOrderStatusAPI(APIView):
    """テーブル注文ステータスポーリング"""
    authentication_classes = []
    permission_classes = []

    def get(self, request, table_id):
        get_object_or_404(TableSeat, pk=table_id, is_active=True)
        orders_key = _get_table_orders_key(table_id)
        order_ids = request.session.get(orders_key, [])

        orders = Order.objects.filter(
            id__in=order_ids
        ).prefetch_related('items__product').order_by('-created_at')

        result = []
        for order in orders:
            items = []
            for it in order.items.all():
                items.append({
                    "id": it.id,
                    "product_name": it.product.name,
                    "qty": it.qty,
                    "unit_price": it.unit_price,
                    "status": it.status,
                    "updated_at": it.updated_at.isoformat(),
                })
            result.append({
                "order_id": order.id,
                "status": order.status,
                "items": items,
                "created_at": order.created_at.isoformat(),
            })

        return Response({"orders": result})
