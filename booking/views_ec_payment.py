"""EC決済フロー: 決済ページ + 注文完了ページ"""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View

from .models import Order, OrderItem


def _get_order_items_with_total(order):
    """注文明細を取得し、各itemにsubtotalを付与して合計も返す"""
    items = list(OrderItem.objects.filter(order=order).select_related('product'))
    total = 0
    for item in items:
        item.subtotal = item.qty * item.unit_price
        total += item.subtotal
    return items, total


class ECPaymentView(View):
    """モック決済ページ（カード情報入力 → 支払確定）"""

    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, channel='ec')

        pending_id = request.session.get('ec_pending_order_id')
        if pending_id != order.id:
            messages.error(request, _('不正なアクセスです。'))
            return redirect('booking:shop')

        if order.payment_status == 'paid':
            return redirect('booking:shop_order_complete', order_id=order.id)

        items, total = _get_order_items_with_total(order)

        return render(request, 'booking/shop_payment.html', {
            'order': order,
            'items': items,
            'total': total,
        })

    def post(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, channel='ec')

        pending_id = request.session.get('ec_pending_order_id')
        if pending_id != order.id:
            messages.error(request, _('不正なアクセスです。'))
            return redirect('booking:shop')

        if order.payment_status == 'paid':
            return redirect('booking:shop_order_complete', order_id=order.id)

        # カード情報バリデーション（形式のみ）
        card_number = request.POST.get('card_number', '').replace(' ', '').replace('-', '')
        card_expiry = request.POST.get('card_expiry', '').strip()
        card_cvv = request.POST.get('card_cvv', '').strip()
        card_name = request.POST.get('card_name', '').strip()

        errors = []
        if not card_number or len(card_number) < 13 or not card_number.isdigit():
            errors.append(_('有効なカード番号を入力してください。'))
        if not card_expiry or len(card_expiry) < 4:
            errors.append(_('有効期限を入力してください。'))
        if not card_cvv or len(card_cvv) < 3 or not card_cvv.isdigit():
            errors.append(_('CVVを入力してください。'))
        if not card_name:
            errors.append(_('カード名義人を入力してください。'))

        if errors:
            items, total = _get_order_items_with_total(order)
            for error in errors:
                messages.error(request, error)
            return render(request, 'booking/shop_payment.html', {
                'order': order,
                'items': items,
                'total': total,
            })

        # モック決済: 即座に成功扱い
        order.payment_status = 'paid'
        order.status = Order.STATUS_CLOSED
        order.save(update_fields=['payment_status', 'status'])

        # セッション更新
        request.session['ec_completed_order_id'] = order.id
        if 'ec_pending_order_id' in request.session:
            del request.session['ec_pending_order_id']

        return redirect('booking:shop_order_complete', order_id=order.id)


class ECOrderConfirmationView(View):
    """注文完了ページ"""

    def get(self, request, order_id):
        order = get_object_or_404(Order, pk=order_id, channel='ec')

        if order.payment_status != 'paid':
            pending_id = request.session.get('ec_pending_order_id')
            if pending_id == order.id:
                return redirect('booking:shop_payment', order_id=order.id)
            return redirect('booking:shop')

        items, total = _get_order_items_with_total(order)

        return render(request, 'booking/shop_order_complete.html', {
            'order': order,
            'items': items,
            'total': total,
        })
