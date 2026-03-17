"""EC注文管理ダッシュボード — 注文一覧・発送管理"""

import json

from django.db.models import Sum, F
from django.http import JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views import View
from django.views.generic import TemplateView

from .models import Order, OrderItem, Staff, Store
from .views_restaurant_dashboard import AdminSidebarMixin


def _get_store(user):
    """ユーザーに紐づく店舗を取得"""
    if user.is_superuser:
        return Store.objects.first()
    try:
        return user.staff.store
    except (Staff.DoesNotExist, AttributeError):
        return Store.objects.first()


class ECOrderDashboardView(AdminSidebarMixin, TemplateView):
    """EC注文管理ダッシュボード"""
    template_name = 'admin/booking/ec_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        store = _get_store(self.request.user)

        ec_orders = Order.objects.filter(
            channel='ec',
        ).select_related('store')
        if store:
            ec_orders = ec_orders.filter(store=store)

        ctx.update({
            'title': _('EC注文管理'),
            'pending_count': ec_orders.filter(shipping_status='pending').count(),
            'shipped_count': ec_orders.filter(shipping_status='shipped').count(),
            'total_count': ec_orders.count(),
            'has_permission': True,
            'site_header': _('管理サイト'),
        })
        return ctx


class ECOrderAPIView(View):
    """EC注文一覧API (JSON)"""

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        store = _get_store(request.user)
        orders = Order.objects.filter(channel='ec').select_related('store')
        if store:
            orders = orders.filter(store=store)

        # フィルタ
        shipping = request.GET.get('shipping', '')
        if shipping and shipping != 'all':
            orders = orders.filter(shipping_status=shipping)

        status = request.GET.get('status', '')
        if status:
            orders = orders.filter(status=status)

        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        if date_from:
            orders = orders.filter(created_at__date__gte=date_from)
        if date_to:
            orders = orders.filter(created_at__date__lte=date_to)

        orders = orders.order_by('-created_at')[:200]

        result = []
        for order in orders:
            items = OrderItem.objects.filter(order=order).select_related('product')
            items_data = [
                {
                    'product_name': item.product.name if item.product else '(削除済)',
                    'qty': item.qty,
                    'unit_price': item.unit_price,
                    'subtotal': item.qty * item.unit_price,
                }
                for item in items
            ]
            total = sum(i['subtotal'] for i in items_data)

            result.append({
                'id': order.id,
                'customer_name': order.customer_name,
                'customer_email': order.customer_email,
                'customer_phone': order.customer_phone,
                'customer_address': order.customer_address,
                'status': order.status,
                'payment_status': order.payment_status,
                'shipping_status': order.shipping_status,
                'tracking_number': order.tracking_number,
                'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
                'shipping_note': order.shipping_note,
                'items': items_data,
                'total': total,
                'created_at': order.created_at.isoformat(),
                'table_label': order.table_label,
            })

        return JsonResponse({'orders': result})


class ECOrderShippingAPIView(View):
    """発送ステータス更新API"""

    def put(self, request, pk):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Unauthorized'}, status=401)

        store = _get_store(request.user)
        try:
            order = Order.objects.get(pk=pk, channel='ec')
        except Order.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)

        if store and order.store_id != store.id:
            return JsonResponse({'error': 'Not found'}, status=404)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        valid_statuses = {c[0] for c in Order.SHIPPING_STATUS_CHOICES}
        new_status = data.get('shipping_status', '')
        if new_status and new_status not in valid_statuses:
            return JsonResponse({'error': 'Invalid shipping status'}, status=400)

        update_fields = []
        if new_status:
            order.shipping_status = new_status
            update_fields.append('shipping_status')
            if new_status == 'shipped' and not order.shipped_at:
                order.shipped_at = timezone.now()
                update_fields.append('shipped_at')

        tracking = data.get('tracking_number')
        if tracking is not None:
            order.tracking_number = tracking
            update_fields.append('tracking_number')

        note = data.get('shipping_note')
        if note is not None:
            order.shipping_note = note
            update_fields.append('shipping_note')

        if update_fields:
            order.save(update_fields=update_fields)

        return JsonResponse({
            'id': order.id,
            'shipping_status': order.shipping_status,
            'tracking_number': order.tracking_number,
            'shipped_at': order.shipped_at.isoformat() if order.shipped_at else None,
            'shipping_note': order.shipping_note,
        })
