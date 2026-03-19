"""Menu & Order views: CustomerMenu, OrderCreate, OrderStatus,
StaffMarkServed, InboundQR, InboundApply, OrderItemStatusUpdate."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.views import generic

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from booking.models import (
    Store, Staff, Product, Category, ProductTranslation,
    Order, OrderItem, StockMovement,
)

logger = logging.getLogger(__name__)


def _resolve_lang(request, store: Store) -> str:
    """言語決定: ?lang=xx があれば優先、なければ店舗既定、最後に ja"""
    lang = request.GET.get("lang")
    if lang:
        return lang
    store_lang = getattr(store, "default_language", None)
    return store_lang or "ja"


def _product_display(product: Product, lang: str) -> dict:
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
    }


class CustomerMenuView(generic.TemplateView):
    """客側メニュー（テンプレ）"""
    template_name = "booking/customer_menu.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = get_object_or_404(Store, pk=self.kwargs["store_id"])
        lang = _resolve_lang(self.request, store)

        categories = Category.objects.filter(store=store).order_by("sort_order", "name")
        products = Product.objects.filter(store=store, is_active=True).select_related("category")

        ctx.update({
            "store": store,
            "lang": lang,
            "categories": categories,
            "products": [_product_display(p, lang) for p in products],
        })
        return ctx


class CustomerMenuJsonAPIView(APIView):
    """客側メニュー（JSON）"""
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        store_id = request.GET.get("store_id")
        if not store_id:
            return Response({"detail": "store_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)
        lang = _resolve_lang(request, store)

        categories = Category.objects.filter(store=store).order_by("sort_order", "name")
        products = Product.objects.filter(store=store, is_active=True).select_related("category")

        return Response({
            "store": {"id": store.id, "name": store.name},
            "lang": lang,
            "categories": [{"id": c.id, "name": c.name} for c in categories],
            "products": [_product_display(p, lang) for p in products],
        })


class ProductAlternativesAPIView(APIView):
    """売切時の代替候補 API"""
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        product_id = request.GET.get("product_id")
        if not product_id:
            return Response({"detail": "product_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        product = get_object_or_404(Product, pk=product_id)
        store = product.store
        lang = _resolve_lang(request, store)

        qs = Product.objects.filter(store=store, is_active=True, stock__gt=0)
        if product.category_id:
            qs = qs.filter(category_id=product.category_id)

        qs = qs.exclude(id=product.id).order_by("-popularity", "price")[:5]
        return Response({"alternatives": [_product_display(p, lang) for p in qs]})


class OrderCreateAPIView(APIView):
    """注文作成（在庫引当=OUT + StockMovement 作成）"""
    authentication_classes = []
    permission_classes = []

    _rate_limit_cache: dict = {}
    _RATE_LIMIT_MAX = 30
    _RATE_LIMIT_WINDOW = 60

    @classmethod
    def _check_order_rate_limit(cls, request) -> bool:
        """Return True if the request should be rate-limited (rejected)."""
        import time as _time
        ip = request.META.get('REMOTE_ADDR', '')
        now = _time.time()
        cls._rate_limit_cache = {
            k: v for k, v in cls._rate_limit_cache.items()
            if now - v['start'] < cls._RATE_LIMIT_WINDOW
        }
        entry = cls._rate_limit_cache.get(ip)
        if entry is None:
            cls._rate_limit_cache[ip] = {'start': now, 'count': 1}
            return False
        if entry['count'] >= cls._RATE_LIMIT_MAX:
            return True
        entry['count'] += 1
        return False

    def post(self, request, *args, **kwargs):
        from django.shortcuts import get_object_or_404
        from booking.models import Schedule

        if self._check_order_rate_limit(request):
            return Response(
                {"detail": "Too many requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        store_id = request.data.get("store_id")
        items = request.data.get("items", [])
        if not items or len(items) > 50:
            return Response({"detail": "items must be 1-50"}, status=status.HTTP_400_BAD_REQUEST)
        schedule_id = request.data.get("schedule_id")

        if not store_id or not isinstance(items, list) or not items:
            return Response({"detail": "store_id and items are required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)
        schedule = get_object_or_404(Schedule, pk=schedule_id) if schedule_id else None
        customer_hash = schedule.line_user_hash if (schedule and schedule.line_user_hash) else None

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
                schedule=schedule,
                customer_line_user_hash=customer_hash,
                status=Order.STATUS_OPEN,
                channel='reservation',
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
                    by_staff=None,
                    note=f"order#{order.id}",
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


class OrderStatusAPIView(APIView):
    """注文状況（客側ポーリング用）"""
    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        order_id = request.GET.get("order_id")
        if not order_id:
            return Response({"detail": "order_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, pk=order_id)

        items = []
        for it in order.items.select_related("product").order_by("created_at"):
            items.append({
                "id": it.id,
                "product_id": it.product_id,
                "product_sku": it.product.sku,
                "product_name": it.product.name,
                "qty": it.qty,
                "unit_price": it.unit_price,
                "status": it.status,
                "updated_at": it.updated_at.isoformat(),
            })

        return Response({
            "order_id": order.id,
            "status": order.status,
            "items": items,
            "updated_at": order.updated_at.isoformat(),
        })


class StaffMarkServedAPIView(LoginRequiredMixin, APIView):
    """スタッフ側: 提供完了"""

    def post(self, request, *args, **kwargs):
        item_id = request.data.get("order_item_id")
        if not item_id:
            return Response({"detail": "order_item_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(OrderItem, pk=item_id)

        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except (Staff.DoesNotExist, AttributeError):
                raise PermissionDenied
            if staff.store_id != item.order.store_id:
                raise PermissionDenied

        item.status = OrderItem.STATUS_SERVED
        item.save(update_fields=["status", "updated_at"])

        return Response({"ok": True, "order_item_id": item.id, "status": item.status})


class InboundQRView(LoginRequiredMixin, generic.TemplateView):
    """入庫QR画面（スタッフ用）"""
    template_name = "booking/inbound_qr.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        sku = self.request.GET.get("sku", "")
        store_id = self.request.GET.get("store_id")

        if store_id:
            store = get_object_or_404(Store, pk=store_id)
        else:
            try:
                store = self.request.user.staff.store
            except (Staff.DoesNotExist, AttributeError):
                store = None

        product = None
        if store and sku:
            product = Product.objects.filter(store=store, sku=sku).first()

        ctx.update({
            "store": store,
            "sku": sku,
            "product": product,
        })
        return ctx


class InboundApplyAPIView(LoginRequiredMixin, APIView):
    """入庫登録 API"""

    def post(self, request, *args, **kwargs):
        sku = request.data.get("sku")
        store_id = request.data.get("store_id")
        try:
            qty = int(request.data.get("qty", 0))
        except Exception:
            qty = 0
        note = request.data.get("note", "")

        if not sku or not store_id or qty <= 0:
            return Response({"detail": "sku, store_id, qty(>0) are required"}, status=status.HTTP_400_BAD_REQUEST)

        store = get_object_or_404(Store, pk=store_id)

        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except (Staff.DoesNotExist, AttributeError):
                raise PermissionDenied
            if staff.store_id != store.id:
                raise PermissionDenied
        else:
            staff = None

        with transaction.atomic():
            try:
                product = Product.objects.select_for_update().get(store=store, sku=sku)
            except Product.DoesNotExist:
                return Response({"detail": "product not found"}, status=status.HTTP_404_NOT_FOUND)

            StockMovement.objects.create(
                store=store,
                product=product,
                movement_type=StockMovement.TYPE_IN,
                qty=qty,
                by_staff=staff,
                note=note,
            )

            Product.objects.filter(pk=product.pk).update(stock=F('stock') + abs(int(qty)))
            product.refresh_from_db(fields=["stock"])

        return Response({"ok": True, "sku": sku, "stock": product.stock})


class OrderItemStatusUpdateAPIView(LoginRequiredMixin, APIView):
    """スタッフ側: 注文アイテムのステータス更新"""

    def post(self, request, item_id, *args, **kwargs):
        new_status = request.data.get("status")
        if not new_status:
            return Response({"detail": "status is required"}, status=status.HTTP_400_BAD_REQUEST)

        preparing = getattr(OrderItem, "STATUS_PREPARING", "PREPARING")

        allowed = {OrderItem.STATUS_ORDERED, preparing, OrderItem.STATUS_SERVED}
        if new_status not in allowed:
            return Response({"detail": "invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        item = get_object_or_404(OrderItem, pk=item_id)

        if not request.user.is_superuser:
            try:
                staff = request.user.staff
            except (Staff.DoesNotExist, AttributeError):
                raise PermissionDenied
            if staff.store_id != item.order.store_id:
                raise PermissionDenied

        current = item.status

        if current == OrderItem.STATUS_SERVED:
            return Response({"detail": "already served"}, status=status.HTTP_409_CONFLICT)

        if current == OrderItem.STATUS_ORDERED and new_status != preparing:
            return Response({"detail": "must transition ORDERED -> PREPARING"}, status=status.HTTP_409_CONFLICT)

        if current == preparing and new_status != OrderItem.STATUS_SERVED:
            return Response({"detail": "must transition PREPARING -> SERVED"}, status=status.HTTP_409_CONFLICT)

        item.status = new_status
        item.save(update_fields=["status", "updated_at"])

        return Response({"ok": True, "order_item_id": item.id, "status": item.status})
