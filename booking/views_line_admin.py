"""LINE管理画面ビュー（セグメント配信・仮予約確認）"""
import json
import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from booking.models import SiteSettings, Store
from booking.models.line_customer import LineCustomer

logger = logging.getLogger(__name__)


class LineSegmentView(View):
    """セグメント配信管理画面"""

    def get(self, request):
        stores = Store.objects.all()
        store_id = request.GET.get('store_id')

        # セグメントごとの件数を集計
        segment_counts = {}
        for seg_key, seg_label in LineCustomer.SEGMENT_CHOICES:
            qs = LineCustomer.objects.filter(segment=seg_key, is_friend=True)
            if store_id:
                qs = qs.filter(store_id=store_id)
            segment_counts[seg_key] = {'label': str(seg_label), 'count': qs.count()}

        context = {
            'title': 'LINEセグメント配信',
            'stores': stores,
            'selected_store_id': int(store_id) if store_id else None,
            'segment_counts': segment_counts,
        }
        return render(request, 'booking/line_admin_segment.html', context)


class LineSegmentSendView(View):
    """セグメント配信実行API"""

    def post(self, request):
        site = SiteSettings.load()
        if not site.line_segment_enabled:
            return JsonResponse({'error': 'セグメント配信が無効です'}, status=400)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': '不正なリクエスト'}, status=400)

        segment = data.get('segment', '')
        message_text = data.get('message', '').strip()
        store_id = data.get('store_id')

        if not message_text:
            return JsonResponse({'error': 'メッセージを入力してください'}, status=400)

        valid_segments = [s[0] for s in LineCustomer.SEGMENT_CHOICES]
        if segment not in valid_segments:
            return JsonResponse({'error': '無効なセグメント'}, status=400)

        # 対象顧客IDを取得
        from booking.services.line_segment import get_customers_by_segment
        customers = get_customers_by_segment(segment, store_id)
        customer_ids = list(customers.values_list('id', flat=True))

        if not customer_ids:
            return JsonResponse({'error': '対象顧客がいません'}, status=400)

        # Celeryタスクで非同期送信
        from booking.tasks import task_send_segment_message
        task_send_segment_message.delay(customer_ids, message_text)

        return JsonResponse({
            'success': True,
            'message': f'{len(customer_ids)}件の配信を開始しました',
        })


class LinePendingView(View):
    """仮予約確認管理画面"""

    def get(self, request):
        from booking.models import Schedule
        schedules = (
            Schedule.objects
            .filter(confirmation_status='pending', is_cancelled=False)
            .select_related('staff', 'store')
            .order_by('start')
        )
        context = {
            'title': '仮予約確認',
            'schedules': schedules,
        }
        return render(request, 'booking/line_admin_pending.html', context)


class LineReservationConfirmView(View):
    """予約確定API"""

    def post(self, request, pk):
        from booking.models import Schedule
        from booking.services.line_bot_service import push_text
        from booking.models.line_customer import LineCustomer

        try:
            schedule = Schedule.objects.select_related('staff', 'store').get(pk=pk)
        except Schedule.DoesNotExist:
            return JsonResponse({'error': '予約が見つかりません'}, status=404)

        if schedule.confirmation_status != 'pending':
            return JsonResponse({'error': 'この予約は確認待ちではありません'}, status=400)

        # 確定
        now = timezone.now()
        staff = None
        try:
            staff = request.user.staff
        except Exception:
            pass

        Schedule.objects.filter(pk=pk).update(
            confirmation_status='confirmed',
            confirmed_at=now,
            confirmed_by=staff,
            is_temporary=False,
        )

        # LINE通知
        if schedule.line_user_enc:
            customer = None
            if schedule.line_user_hash:
                customer = LineCustomer.objects.filter(line_user_hash=schedule.line_user_hash).first()
            local_start = timezone.localtime(schedule.start)
            store_name = schedule.store.name if schedule.store else ''
            push_text(
                schedule.line_user_enc,
                f'【ご予約が確定しました】\n\n'
                f'日時: {local_start:%Y/%m/%d %H:%M}\n'
                f'担当: {schedule.staff.name}\n'
                f'店舗: {store_name}\n'
                f'予約番号: {schedule.reservation_number}\n\n'
                f'ご来店をお待ちしております。',
                message_type='system',
                customer=customer,
            )

        return JsonResponse({'success': True, 'message': '予約を確定しました'})


class LineReservationRejectView(View):
    """予約却下API"""

    def post(self, request, pk):
        import json as _json
        from booking.models import Schedule
        from booking.services.line_bot_service import push_text
        from booking.models.line_customer import LineCustomer

        try:
            schedule = Schedule.objects.select_related('staff', 'store').get(pk=pk)
        except Schedule.DoesNotExist:
            return JsonResponse({'error': '予約が見つかりません'}, status=404)

        if schedule.confirmation_status != 'pending':
            return JsonResponse({'error': 'この予約は確認待ちではありません'}, status=400)

        try:
            data = _json.loads(request.body)
        except (ValueError, _json.JSONDecodeError):
            data = {}

        reason = data.get('reason', '').strip()[:200]
        staff = None
        try:
            staff = request.user.staff
        except Exception:
            pass

        Schedule.objects.filter(pk=pk).update(
            confirmation_status='rejected',
            confirmed_at=timezone.now(),
            confirmed_by=staff,
            rejection_reason=reason,
            is_cancelled=True,
        )

        # LINE通知
        if schedule.line_user_enc:
            customer = None
            if schedule.line_user_hash:
                customer = LineCustomer.objects.filter(line_user_hash=schedule.line_user_hash).first()
            message = '【ご予約をお受けできませんでした】\n\n申し訳ございません。ご希望の日時でのご予約をお受けできませんでした。'
            if reason:
                message += f'\n理由: {reason}'
            message += '\n\n別の日時での予約をご検討ください。'
            push_text(
                schedule.line_user_enc, message,
                message_type='system', customer=customer,
            )

        return JsonResponse({'success': True, 'message': '予約を却下しました'})
