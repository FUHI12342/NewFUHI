"""EC Shop views: ShopView, CartView, CartAddAPIView, CartUpdateAPIView,
CartRemoveAPIView, ShopCheckoutView, ShopConfirmView, and helpers."""
import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import (
    Product, Category, Order, OrderItem, StockMovement,
)

logger = logging.getLogger(__name__)


def _resolve_lang(request, store) -> str:
    """言語決定: ?lang=xx があれば優先、なければ店舗既定、最後に ja"""
    lang = request.GET.get("lang")
    if lang:
        return lang
    store_lang = getattr(store, "default_language", None)
    return store_lang or "ja"


def _is_placeholder_image(product) -> bool:
    """seed コマンドで生成されたプレースホルダー画像かどうかを判定。
    seed は '{sku.lower()}.png' で保存するが、Django Storage が
    重複回避で '{sku.lower()}_{hash}.png' にリネームする場合がある。
    """
    if not product.image:
        return False
    filename = product.image.name.rsplit("/", 1)[-1] if product.image.name else ""
    sku_lower = product.sku.lower()
    # 完全一致 or Django Storage のランダムサフィックス付き
    return (
        filename == f"{sku_lower}.png"
        or filename.startswith(f"{sku_lower}_") and filename.endswith(".png")
    )


def _product_display(product, lang: str) -> dict:
    tr = product.translations.filter(lang=lang).first()
    return {
        "id": product.id,
        "sku": product.sku,
        "name": tr.name if tr else product.name,
        "description": tr.description if tr else product.description,
        "price": product.price,
        "stock": product.stock,
        "is_sold_out": (product.stock <= 0),
        "category_id": product.category_id,
        "image_url": product.image.url if product.image else "",
        "is_placeholder_image": _is_placeholder_image(product),
    }


def get_shipping_fee(store, subtotal):
    """送料計算"""
    try:
        config = store.shipping_config
    except Exception:
        return 0
    if not config.is_enabled:
        return 0
    if config.free_shipping_threshold > 0 and subtotal >= config.free_shipping_threshold:
        return 0
    return config.shipping_fee


def _build_cart_context(cart, store=None):
    """カートからcart_items, subtotal, shipping_fee, totalを構築"""
    cart_items = []
    subtotal = 0
    for product_id, item in cart.items():
        item_subtotal = item['price'] * item['qty']
        cart_items.append({
            'product_id': product_id,
            'name': item['name'],
            'price': item['price'],
            'qty': item['qty'],
            'subtotal': item_subtotal,
        })
        subtotal += item_subtotal

    shipping_fee = 0
    if store:
        shipping_fee = get_shipping_fee(store, subtotal)

    return {
        'cart_items': cart_items,
        'subtotal': subtotal,
        'shipping_fee': shipping_fee,
        'total': subtotal + shipping_fee,
        'store': store,
    }


def _get_store_from_cart(cart):
    """カートの最初の商品からstoreを取得"""
    if not cart:
        return None
    first_pid = list(cart.keys())[0]
    try:
        return Product.objects.get(pk=first_pid).store
    except Product.DoesNotExist:
        return None


class ShopView(View):
    """ショップページ（EC公開商品の一覧）"""
    def get(self, request):
        from django.utils.translation import get_language
        lang = get_language() or 'ja'

        products = Product.objects.filter(
            is_active=True,
            is_ec_visible=True,
        ).select_related('category', 'store').prefetch_related('translations')

        category_id = request.GET.get('category')
        if category_id:
            products = products.filter(category_id=category_id)

        search_q = request.GET.get('q', '').strip()
        if search_q:
            products = products.filter(
                Q(name__icontains=search_q) | Q(sku__icontains=search_q)
            )

        categories = Category.objects.filter(
            products__is_active=True,
            products__is_ec_visible=True,
        ).distinct().order_by('sort_order', 'name')

        product_list = [_product_display(p, lang) for p in products]

        cart = request.session.get('ec_cart', {})
        cart_count = sum(item.get('qty', 0) for item in cart.values())

        return render(request, 'booking/shop.html', {
            'products': product_list,
            'categories': categories,
            'current_category': category_id,
            'search_q': search_q,
            'cart_count': cart_count,
        })


class CartView(View):
    """カートページ"""
    def get(self, request):
        cart = request.session.get('ec_cart', {})
        store = _get_store_from_cart(cart)
        ctx = _build_cart_context(cart, store)

        if store:
            try:
                config = store.shipping_config
                if config.is_enabled and config.free_shipping_threshold > 0 and ctx['subtotal'] < config.free_shipping_threshold:
                    ctx['free_shipping_remaining'] = config.free_shipping_threshold - ctx['subtotal']
                if config.is_enabled and config.note:
                    ctx['shipping_note'] = config.note
            except Exception:
                pass

        return render(request, 'booking/shop_cart.html', ctx)


class CartAddAPIView(APIView):
    """カートに商品追加 API (公開・セッションベース)"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        product_id = str(request.data.get('product_id', ''))
        try:
            qty = int(request.data.get('qty', 1))
        except (ValueError, TypeError):
            return Response({'status': 'error', 'message': '数量が不正です'}, status=400)

        try:
            product = Product.objects.get(pk=product_id, is_active=True, is_ec_visible=True)
        except Product.DoesNotExist:
            return Response({'status': 'error', 'message': '商品が見つかりません'}, status=404)

        if product.stock < qty:
            return Response({'status': 'error', 'message': '在庫が不足しています'}, status=400)

        cart = request.session.get('ec_cart', {})
        if product_id in cart:
            cart[product_id]['qty'] += qty
        else:
            from django.utils.translation import get_language
            lang = get_language() or 'ja'
            tr = product.translations.filter(lang=lang).first()
            cart[product_id] = {
                'name': tr.name if tr else product.name,
                'price': product.price,
                'qty': qty,
            }
        request.session['ec_cart'] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class CartUpdateAPIView(APIView):
    """カート数量変更 API (公開・セッションベース)"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        product_id = str(request.data.get('product_id', ''))
        try:
            qty = int(request.data.get('qty', 0))
        except (ValueError, TypeError):
            return Response({'status': 'error', 'message': '数量が不正です'}, status=400)

        cart = request.session.get('ec_cart', {})
        if product_id not in cart:
            return Response({'status': 'error', 'message': 'カートにない商品です'}, status=404)

        if qty <= 0:
            del cart[product_id]
        else:
            cart[product_id]['qty'] = qty
        request.session['ec_cart'] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class CartRemoveAPIView(APIView):
    """カートから商品削除 API (公開・セッションベース)"""
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        product_id = str(request.data.get('product_id', ''))

        cart = request.session.get('ec_cart', {})
        if product_id in cart:
            del cart[product_id]
        request.session['ec_cart'] = cart
        cart_count = sum(item['qty'] for item in cart.values())
        return Response({'status': 'ok', 'cart_count': cart_count})


class ShopCheckoutView(View):
    """チェックアウトページ"""
    def get(self, request):
        cart = request.session.get('ec_cart', {})
        if not cart:
            return redirect('booking:shop')

        store = _get_store_from_cart(cart)
        ctx = _build_cart_context(cart, store)

        customer = request.session.get('ec_customer', {})
        ctx.update(customer)

        if store:
            try:
                config = store.shipping_config
                if config.is_enabled and config.free_shipping_threshold > 0 and ctx['subtotal'] < config.free_shipping_threshold:
                    ctx['free_shipping_remaining'] = config.free_shipping_threshold - ctx['subtotal']
                if config.is_enabled and config.note:
                    ctx['shipping_note'] = config.note
            except Exception:
                pass

        return render(request, 'booking/shop_checkout.html', ctx)

    def post(self, request):
        """フォーム入力 -> セッションに保存 -> 確認画面へ"""
        cart = request.session.get('ec_cart', {})
        if not cart:
            return redirect('booking:shop')

        customer_name = request.POST.get('customer_name', '').strip()
        customer_email = request.POST.get('customer_email', '').strip()
        customer_phone = request.POST.get('customer_phone', '').strip()
        customer_address = request.POST.get('customer_address', '').strip()

        if not customer_name or not customer_email:
            messages.error(request, 'お名前とメールアドレスは必須です。')
            return redirect('booking:shop_checkout')

        request.session['ec_customer'] = {
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
        }
        return redirect('booking:shop_confirm')


class ShopConfirmView(View):
    """注文確認画面"""
    def get(self, request):
        cart = request.session.get('ec_cart', {})
        customer = request.session.get('ec_customer', {})
        if not cart or not customer:
            return redirect('booking:shop_checkout')

        store = _get_store_from_cart(cart)
        ctx = _build_cart_context(cart, store)
        ctx.update(customer)

        if store:
            try:
                config = store.shipping_config
                if config.is_enabled and config.free_shipping_threshold > 0 and ctx['subtotal'] < config.free_shipping_threshold:
                    ctx['free_shipping_remaining'] = config.free_shipping_threshold - ctx['subtotal']
                if config.is_enabled and config.note:
                    ctx['shipping_note'] = config.note
            except Exception:
                pass

        return render(request, 'booking/shop_confirm.html', ctx)

    def post(self, request):
        """注文確定"""
        cart = request.session.get('ec_cart', {})
        customer = request.session.get('ec_customer', {})
        if not cart or not customer:
            return redirect('booking:shop_checkout')

        customer_name = customer.get('customer_name', '')
        customer_email = customer.get('customer_email', '')
        customer_phone = customer.get('customer_phone', '')
        customer_address = customer.get('customer_address', '')

        with transaction.atomic():
            first_pid = list(cart.keys())[0]
            try:
                first_product = Product.objects.get(pk=first_pid)
            except Product.DoesNotExist:
                messages.error(request, '商品が見つかりません。')
                return redirect('booking:shop_cart')

            store = first_product.store

            subtotal = sum(item['price'] * item['qty'] for item in cart.values())
            shipping_fee = get_shipping_fee(store, subtotal)

            order = Order.objects.create(
                store=store,
                status=Order.STATUS_OPEN,
                table_label=f'EC: {customer_name}',
                channel='ec',
                customer_name=customer_name,
                customer_email=customer_email,
                customer_phone=customer_phone,
                customer_address=customer_address,
                shipping_status='pending',
                shipping_fee=shipping_fee,
            )

            for product_id, item in cart.items():
                product = Product.objects.select_for_update().get(pk=product_id)
                qty = item['qty']

                if product.stock < qty:
                    messages.error(request, f'{product.name} の在庫が不足しています。')
                    return redirect('booking:shop_cart')

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    qty=qty,
                    unit_price=product.price,
                )

                Product.objects.filter(pk=product.pk).update(stock=F('stock') - abs(int(qty)))
                product.refresh_from_db(fields=['stock'])

                StockMovement.objects.create(
                    store=product.store,
                    product=product,
                    movement_type=StockMovement.TYPE_OUT,
                    qty=qty,
                    note=f'EC order #{order.id}',
                )

        request.session['ec_cart'] = {}
        request.session.pop('ec_customer', None)
        request.session['ec_pending_order_id'] = order.id
        return redirect('booking:shop_payment', order_id=order.id)
