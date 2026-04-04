"""LINE Webhook 受信エンドポイント"""
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

# Webhook handler singleton
_webhook_handler = None


def _get_webhook_handler():
    """WebhookHandler シングルトンを返す"""
    global _webhook_handler
    if _webhook_handler is not None:
        return _webhook_handler

    from linebot import WebhookHandler
    channel_secret = getattr(settings, 'LINE_CHANNEL_SECRET', None)
    if not channel_secret:
        raise ValueError("LINE_CHANNEL_SECRET is not set")

    _webhook_handler = WebhookHandler(channel_secret)
    _register_handlers(_webhook_handler)
    return _webhook_handler


def _register_handlers(handler):
    """イベントハンドラを登録"""
    from linebot.models import (
        FollowEvent, UnfollowEvent, MessageEvent, TextMessage, PostbackEvent,
    )

    @handler.add(FollowEvent)
    def handle_follow(event):
        """友だち追加"""
        from booking.services.line_bot_service import get_customer_or_create, reply_text
        line_user_id = event.source.user_id
        customer, created = get_customer_or_create(line_user_id)
        reply_text(
            event.reply_token,
            'お友だち追加ありがとうございます！\nこちらからご予約の確認やお知らせをお送りします。',
        )
        logger.info("LINE follow: customer=%s created=%s", customer, created)

    @handler.add(UnfollowEvent)
    def handle_unfollow(event):
        """ブロック"""
        from booking.models.schedule import Schedule
        from booking.models.line_customer import LineCustomer
        from django.utils import timezone

        line_user_hash = Schedule.make_line_user_hash(event.source.user_id)
        LineCustomer.objects.filter(line_user_hash=line_user_hash).update(
            is_friend=False, blocked_at=timezone.now(),
        )
        logger.info("LINE unfollow: hash=%s", line_user_hash[:8])

    @handler.add(MessageEvent, message=TextMessage)
    def handle_text_message(event):
        """テキストメッセージ受信"""
        from booking.models import SiteSettings
        site = SiteSettings.load()

        # チャットボットが有効な場合のみ処理
        if site.line_chatbot_enabled:
            from booking.services.line_chatbot import handle_chat_message
            handle_chat_message(event)
        else:
            from booking.services.line_bot_service import reply_text
            reply_text(
                event.reply_token,
                'こちらはご予約専用アカウントです。\nご予約はWebサイトからお願いいたします。',
            )

    @handler.add(PostbackEvent)
    def handle_postback(event):
        """Postbackイベント（リッチメニュー等）"""
        from booking.services.line_bot_service import reply_text
        import urllib.parse

        data = urllib.parse.parse_qs(event.postback.data)
        action = data.get('action', [''])[0]

        if action == 'start_booking':
            _handle_start_booking(event)
        elif action == 'check_booking':
            _handle_check_booking(event)
        elif action == 'contact':
            reply_text(event.reply_token, 'お問い合わせはWebサイトの問い合わせフォームからお願いいたします。')
        else:
            logger.warning("Unknown postback action: %s", action)


def _handle_start_booking(event):
    """予約開始ハンドラ"""
    from booking.models import SiteSettings
    site = SiteSettings.load()

    if site.line_chatbot_enabled:
        from booking.services.line_chatbot import start_booking_flow
        start_booking_flow(event)
    else:
        from booking.services.line_bot_service import reply_text
        reply_text(event.reply_token, 'ご予約はWebサイトからお願いいたします。')


def _handle_check_booking(event):
    """予約確認ハンドラ"""
    from booking.models.schedule import Schedule
    from booking.services.line_bot_service import reply_text
    from django.utils import timezone

    line_user_hash = Schedule.make_line_user_hash(event.source.user_id)
    now = timezone.now()

    upcoming = Schedule.objects.filter(
        line_user_hash=line_user_hash,
        start__gte=now,
        is_cancelled=False,
        is_temporary=False,
    ).select_related('staff', 'store').order_by('start')[:3]

    if not upcoming:
        reply_text(event.reply_token, '現在、直近のご予約はありません。')
        return

    lines = ['【ご予約情報】']
    for s in upcoming:
        local_start = timezone.localtime(s.start)
        store_name = s.store.name if s.store else ''
        lines.append(
            f'\n📅 {local_start:%Y/%m/%d %H:%M}\n'
            f'担当: {s.staff.name}\n'
            f'店舗: {store_name}\n'
            f'予約番号: {s.reservation_number}'
        )
    reply_text(event.reply_token, '\n'.join(lines))


@csrf_exempt
@require_POST
def line_webhook(request):
    """LINE Webhook 受信"""
    signature = request.META.get('HTTP_X_LINE_SIGNATURE', '')
    if not signature:
        return HttpResponseForbidden('Missing signature')

    body = request.body.decode('utf-8')

    try:
        handler = _get_webhook_handler()
        handler.handle(body, signature)
    except Exception as e:
        logger.error("LINE webhook error: %s", e)
        return HttpResponseBadRequest('Invalid request')

    return HttpResponse('OK')
