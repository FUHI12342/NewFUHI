"""LINE Messaging API 共通サービス"""
import logging
import time

from django.conf import settings

logger = logging.getLogger(__name__)


def _get_bot_api():
    """LineBotApi インスタンスを返す"""
    from linebot import LineBotApi
    access_token = getattr(settings, 'LINE_ACCESS_TOKEN', None)
    if not access_token:
        raise ValueError("LINE_ACCESS_TOKEN is not set")
    return LineBotApi(access_token)


def _decrypt_line_user_id(line_user_enc):
    """暗号化されたLINE user_idを復号"""
    from booking.models.schedule import Schedule
    f = Schedule._get_line_id_fernet()
    return f.decrypt(line_user_enc.encode('utf-8')).decode('utf-8')


def _log_message(customer, message_type, content_preview, status='sent', error_detail=''):
    """送信ログを記録"""
    from booking.models.line_customer import LineMessageLog
    LineMessageLog.objects.create(
        customer=customer,
        message_type=message_type,
        content_preview=content_preview[:200],
        status=status,
        error_detail=error_detail,
    )


def push_text(line_user_enc, message, message_type='system', customer=None, max_retries=3):
    """テキストメッセージをpush送信（復号→送信→ログ記録）

    Args:
        line_user_enc: 暗号化されたLINE user_id
        message: 送信テキスト
        message_type: ログ記録用の種別
        customer: LineCustomer instance (optional)
        max_retries: リトライ回数

    Returns:
        True=成功, False=失敗
    """
    from linebot.models import TextSendMessage

    try:
        line_user_id = _decrypt_line_user_id(line_user_enc)
    except Exception as e:
        logger.error("LINE user_id decryption failed: %s", e)
        _log_message(customer, message_type, message, status='failed', error_detail=str(e))
        return False

    bot = _get_bot_api()
    for attempt in range(max_retries):
        try:
            bot.push_message(line_user_id, TextSendMessage(text=message))
            _log_message(customer, message_type, message)
            return True
        except Exception as e:
            logger.warning(
                "LINE push attempt %d/%d failed: %s", attempt + 1, max_retries, e,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    _log_message(customer, message_type, message, status='failed', error_detail='Max retries exceeded')
    return False


def reply_text(reply_token, message):
    """reply_token を使ってテキスト返信"""
    from linebot.models import TextSendMessage

    try:
        bot = _get_bot_api()
        bot.reply_message(reply_token, TextSendMessage(text=message))
        return True
    except Exception as e:
        logger.error("LINE reply failed: %s", e)
        return False


def push_flex(line_user_enc, alt_text, flex_container, message_type='system', customer=None, max_retries=3):
    """Flex Messageをpush送信"""
    from linebot.models import FlexSendMessage

    try:
        line_user_id = _decrypt_line_user_id(line_user_enc)
    except Exception as e:
        logger.error("LINE user_id decryption failed: %s", e)
        _log_message(customer, message_type, alt_text, status='failed', error_detail=str(e))
        return False

    bot = _get_bot_api()
    for attempt in range(max_retries):
        try:
            bot.push_message(
                line_user_id,
                FlexSendMessage(alt_text=alt_text, contents=flex_container),
            )
            _log_message(customer, message_type, alt_text)
            return True
        except Exception as e:
            logger.warning(
                "LINE flex push attempt %d/%d failed: %s", attempt + 1, max_retries, e,
            )
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    _log_message(customer, message_type, alt_text, status='failed', error_detail='Max retries exceeded')
    return False


def get_customer_or_create(line_user_id, display_name='', store=None):
    """LineCustomer を取得/作成

    Args:
        line_user_id: 生のLINE user_id
        display_name: LINE表示名
        store: Store instance (optional)

    Returns:
        (LineCustomer, created)
    """
    from booking.models.schedule import Schedule
    from booking.models.line_customer import LineCustomer

    line_user_hash = Schedule.make_line_user_hash(line_user_id)

    try:
        customer = LineCustomer.objects.get(line_user_hash=line_user_hash)
        updated_fields = []
        if display_name and customer.display_name != display_name:
            customer.display_name = display_name
            updated_fields.append('display_name')
        if store and customer.store_id != store.id:
            customer.store = store
            updated_fields.append('store')
        if not customer.is_friend:
            customer.is_friend = True
            customer.blocked_at = None
            updated_fields.extend(['is_friend', 'blocked_at'])
        if updated_fields:
            customer.save(update_fields=updated_fields + ['last_visit_at'])
        return customer, False
    except LineCustomer.DoesNotExist:
        pass

    # Encrypt user_id
    f = Schedule._get_line_id_fernet()
    line_user_enc = f.encrypt(line_user_id.encode('utf-8')).decode('utf-8')

    customer = LineCustomer.objects.create(
        line_user_hash=line_user_hash,
        line_user_enc=line_user_enc,
        display_name=display_name,
        store=store,
    )
    return customer, True
