"""EC決済フロー: 決済ページ + 注文完了ページ"""
import json
import logging

import requests
from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View

from .models import Order, OrderItem, PaymentMethod

logger = logging.getLogger(__name__)


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

        # Coiney が有効なら Coiney Payge へリダイレクト
        coiney_method = PaymentMethod.objects.filter(
            store=order.store, method_type='coiney', is_enabled=True
        ).first()

        if coiney_method:
            redirect_url = self._try_coiney_redirect(request, order, coiney_method)
            if redirect_url:
                return redirect(redirect_url)

        # Coiney 未設定 or API失敗時はモック決済フォーム
        items, total = _get_order_items_with_total(order)

        return render(request, 'booking/shop_payment.html', {
            'order': order,
            'items': items,
            'total': total,
        })

    @staticmethod
    def _try_coiney_redirect(request, order, coiney_method):
        """Coiney Payge API を呼び出し、決済URLを返す。失敗時は None。"""
        items, total = _get_order_items_with_total(order)
        payment_api_url = coiney_method.api_endpoint or settings.PAYMENT_API_URL
        api_key = coiney_method.api_key or settings.PAYMENT_API_KEY
        headers = {
            'Authorization': 'Bearer ' + api_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-CoineyPayge-Version': '2016-10-25',
        }
        _wh_token = f"?token={settings.COINEY_WEBHOOK_TOKEN}" if settings.COINEY_WEBHOOK_TOKEN else ""
        webhook_url = f"{settings.WEBHOOK_URL_BASE}ec_order_{order.id}/{_wh_token}"
        cancel_url = request.build_absolute_uri(
            reverse('booking:shop_payment', kwargs={'order_id': order.id})
        )
        data = {
            "amount": total,
            "currency": "jpy",
            "locale": "ja_JP",
            "cancelUrl": cancel_url,
            "webhookUrl": webhook_url,
            "method": "creditcard",
            "subject": f"ECオーダー #{order.id}",
            "description": f"EC注文 #{order.id}",
            "metadata": {"orderId": f"ec_order_{order.id}"},
        }

        try:
            response = requests.post(
                payment_api_url, headers=headers, data=json.dumps(data)
            )
            if response.status_code == 201:
                payment_url = response.json().get('links', {}).get('paymentUrl')
                if payment_url:
                    return payment_url
        except Exception as e:
            logger.error("Coiney API error for EC order #%s: %s", order.id, e)

        return None

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


def process_ec_payment(request, orderId):
    """Coiney webhook から呼ばれる EC注文の決済完了処理"""
    body = json.loads(request.body)
    if body.get('type') != 'payment.succeeded':
        return JsonResponse({"status": "ignored"})

    order_id = orderId.replace('ec_order_', '')
    try:
        order = Order.objects.get(pk=order_id, channel='ec')
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found"}, status=404)

    order.payment_status = 'paid'
    order.status = Order.STATUS_CLOSED
    order.save(update_fields=['payment_status', 'status'])
    return JsonResponse({"status": "success"})
