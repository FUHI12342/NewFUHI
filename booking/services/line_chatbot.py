"""LINEチャットボット予約エンジン

状態機械:
idle -> select_store -> select_staff -> select_date -> select_time -> confirm -> idle
10分タイムアウトで idle に自動リセット
"""
import logging
from datetime import datetime, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# 会話状態管理（LineCustomer.tags に保存）
CHATBOT_STATE_KEY = 'chatbot_state'
CHATBOT_DATA_KEY = 'chatbot_data'
CHATBOT_TIMESTAMP_KEY = 'chatbot_ts'
STATE_TIMEOUT_MINUTES = 10

# キャンセルキーワード
_CANCEL_KEYWORDS = frozenset(('キャンセル', 'やめる', 'cancel', 'リセット'))
# 予約開始キーワード
_BOOKING_KEYWORDS = ('予約', '予約する', 'book')
# 確定キーワード
_CONFIRM_YES = frozenset(('はい', 'yes', 'ok', 'はい。', 'OK'))
_CONFIRM_NO = frozenset(('いいえ', 'no', 'いいえ。', 'やめる'))

_WEEKDAY_NAMES = ('月', '火', '水', '木', '金', '土', '日')


def _get_tags_as_dict(customer):
    """tags フィールドを安全に dict として取得する"""
    tags = customer.tags
    if isinstance(tags, dict):
        return tags
    return {}


def _get_state(customer):
    """顧客の会話状態を取得（タイムアウトチェック付き）

    Returns:
        (state: str, data: dict)
    """
    tags = _get_tags_as_dict(customer)
    state = tags.get(CHATBOT_STATE_KEY, 'idle')
    ts = tags.get(CHATBOT_TIMESTAMP_KEY)

    if state != 'idle' and ts:
        try:
            last_time = datetime.fromisoformat(ts)
            # タイムゾーンなし（naive）の場合はローカルタイムゾーンとしてaware化
            if last_time.tzinfo is None:
                last_time = timezone.make_aware(last_time)
            elapsed = (timezone.now() - last_time).total_seconds()
            if elapsed > STATE_TIMEOUT_MINUTES * 60:
                _set_state(customer, 'idle')
                return 'idle', {}
        except (ValueError, TypeError):
            pass

    data = tags.get(CHATBOT_DATA_KEY, {})
    return state, data


def _set_state(customer, state, data=None):
    """会話状態を更新（immutableパターン: 新しいdictを作成してDB更新）"""
    from booking.models.line_customer import LineCustomer

    old_tags = _get_tags_as_dict(customer)
    new_tags = {
        **old_tags,
        CHATBOT_STATE_KEY: state,
        CHATBOT_DATA_KEY: data or {},
        CHATBOT_TIMESTAMP_KEY: timezone.now().isoformat(),
    }
    LineCustomer.objects.filter(pk=customer.pk).update(tags=new_tags)
    customer.tags = new_tags


def handle_chat_message(event):
    """テキストメッセージを会話エンジンに振り分け"""
    from booking.services.line_bot_service import get_customer_or_create, reply_text

    line_user_id = event.source.user_id
    customer, _ = get_customer_or_create(line_user_id)

    text = event.message.text.strip()
    state, data = _get_state(customer)

    # 「キャンセル」「やめる」で即座にidle
    if text in _CANCEL_KEYWORDS:
        _set_state(customer, 'idle')
        reply_text(event.reply_token, '予約操作をキャンセルしました。')
        return

    # 「予約」キーワードで予約フロー開始
    if state == 'idle' and any(kw in text for kw in _BOOKING_KEYWORDS):
        start_booking_flow(event)
        return

    handlers = {
        'select_store': _handle_select_store,
        'select_staff': _handle_select_staff,
        'select_date': _handle_select_date,
        'select_time': _handle_select_time,
        'confirm': _handle_confirm,
    }

    handler = handlers.get(state)
    if handler:
        handler(event, customer, text, data)
    else:
        reply_text(
            event.reply_token,
            '「予約」と入力すると予約を開始できます。\n'
            '「キャンセル」で操作を中断できます。',
        )


def start_booking_flow(event):
    """予約フロー開始（Postback/テキストから呼ばれる）"""
    from booking.models import Store
    from booking.services.line_bot_service import get_customer_or_create, reply_text

    line_user_id = event.source.user_id
    customer, _ = get_customer_or_create(line_user_id)

    stores = list(Store.objects.all().values('id', 'name'))

    if not stores:
        reply_text(event.reply_token, '現在予約可能な店舗がありません。')
        return

    if len(stores) == 1:
        # 店舗が1つなら自動選択してスタッフ選択へ
        store = stores[0]
        _set_state(customer, 'select_staff', {
            'store_id': store['id'],
            'store_name': store['name'],
        })
        _show_staff_list(event, store['id'], customer)
        return

    # 複数店舗: 店舗選択
    _set_state(customer, 'select_store')
    lines = ['【店舗を選択してください】\n']
    for i, s in enumerate(stores, 1):
        lines.append(f'{i}. {s["name"]}')
    lines.append('\n番号を入力してください。')
    reply_text(event.reply_token, '\n'.join(lines))


def _handle_select_store(event, customer, text, data):
    """店舗選択ハンドラ"""
    from booking.models import Store
    from booking.services.line_bot_service import reply_text

    stores = list(Store.objects.all().values('id', 'name'))
    try:
        idx = int(text) - 1
        if 0 <= idx < len(stores):
            store = stores[idx]
            _set_state(customer, 'select_staff', {
                'store_id': store['id'],
                'store_name': store['name'],
            })
            _show_staff_list(event, store['id'], customer)
            return
    except ValueError:
        pass

    reply_text(event.reply_token, '番号で店舗を選択してください。')


def _show_staff_list(event, store_id, customer):
    """スタッフ一覧を表示"""
    from booking.models import Staff
    from booking.services.line_bot_service import reply_text

    staffs = list(
        Staff.objects
        .filter(store_id=store_id, staff_type='fortune_teller')
        .values('id', 'name', 'price')
    )

    if not staffs:
        _set_state(customer, 'idle')
        reply_text(event.reply_token, '現在予約可能なスタッフがいません。')
        return

    lines = ['【スタッフを選択してください】\n']
    for i, s in enumerate(staffs, 1):
        lines.append(f'{i}. {s["name"]} ({s["price"]}円)')
    lines.append('\n番号を入力してください。')
    reply_text(event.reply_token, '\n'.join(lines))


def _handle_select_staff(event, customer, text, data):
    """スタッフ選択ハンドラ"""
    from booking.models import Staff
    from booking.services.line_bot_service import reply_text

    store_id = data.get('store_id')
    staffs = list(
        Staff.objects
        .filter(store_id=store_id, staff_type='fortune_teller')
        .values('id', 'name', 'price')
    )

    try:
        idx = int(text) - 1
        if 0 <= idx < len(staffs):
            staff = staffs[idx]
            new_data = {
                **data,
                'staff_id': staff['id'],
                'staff_name': staff['name'],
                'price': staff['price'],
            }
            _set_state(customer, 'select_date', new_data)
            _show_available_dates(event, staff['id'], store_id, customer)
            return
    except ValueError:
        pass

    reply_text(event.reply_token, '番号でスタッフを選択してください。')


def _show_available_dates(event, staff_id, store_id, customer):
    """空き日付を表示"""
    from booking.models import Staff, Store
    from booking.services.availability import get_available_dates
    from booking.services.line_bot_service import reply_text

    staff = Staff.objects.get(id=staff_id)
    store = Store.objects.filter(id=store_id).first()
    dates = get_available_dates(staff, store, days_ahead=14)

    if not dates:
        reply_text(
            event.reply_token,
            '2週間以内に空きがありません。別のスタッフをお試しください。',
        )
        _set_state(customer, 'idle')
        return

    lines = ['【日付を選択してください】\n']
    for i, d in enumerate(dates[:7], 1):  # 最大7日表示
        wd = _WEEKDAY_NAMES[d.weekday()]
        lines.append(f'{i}. {d:%m/%d}({wd})')
    lines.append('\n番号を入力してください。')
    reply_text(event.reply_token, '\n'.join(lines))


def _handle_select_date(event, customer, text, data):
    """日付選択ハンドラ"""
    import datetime as dt
    from booking.models import Staff, Store
    from booking.services.availability import get_available_dates, get_available_slots
    from booking.services.line_bot_service import reply_text

    staff_id = data.get('staff_id')
    store_id = data.get('store_id')
    staff = Staff.objects.get(id=staff_id)
    store = Store.objects.filter(id=store_id).first()
    dates = get_available_dates(staff, store, days_ahead=14)[:7]

    try:
        idx = int(text) - 1
        if 0 <= idx < len(dates):
            selected_date = dates[idx]
            new_data = {
                **data,
                'date': selected_date.isoformat(),
            }
            _set_state(customer, 'select_time', new_data)

            # 空き時間を表示
            slots = get_available_slots(staff, selected_date, store)
            lines = [f'【{selected_date:%m/%d} の空き時間】\n']
            for i, slot in enumerate(slots[:10], 1):  # 最大10枠
                lines.append(f'{i}. {slot["label"]}')
            lines.append('\n番号を入力してください。')
            reply_text(event.reply_token, '\n'.join(lines))
            return
    except ValueError:
        pass

    reply_text(event.reply_token, '番号で日付を選択してください。')


def _handle_select_time(event, customer, text, data):
    """時間選択ハンドラ"""
    import datetime as dt
    from booking.models import Staff, Store
    from booking.services.availability import get_available_slots
    from booking.services.line_bot_service import reply_text

    staff_id = data.get('staff_id')
    store_id = data.get('store_id')
    date_str = data.get('date')
    selected_date = dt.date.fromisoformat(date_str)

    staff = Staff.objects.get(id=staff_id)
    store = Store.objects.filter(id=store_id).first()
    slots = get_available_slots(staff, selected_date, store)[:10]

    try:
        idx = int(text) - 1
        if 0 <= idx < len(slots):
            slot = slots[idx]
            new_data = {
                **data,
                'hour': slot['hour'],
                'minute': slot['minute'],
                'time_label': slot['label'],
            }
            _set_state(customer, 'confirm', new_data)

            # 確認メッセージ
            wd = _WEEKDAY_NAMES[selected_date.weekday()]
            message = (
                f'【予約内容の確認】\n\n'
                f'店舗: {data.get("store_name", "")}\n'
                f'スタッフ: {data.get("staff_name", "")}\n'
                f'日時: {selected_date:%Y/%m/%d}({wd}) {slot["label"]}\n'
                f'料金: {data.get("price", 0)}円\n\n'
                f'この内容で予約しますか？\n'
                f'「はい」で予約確定\n'
                f'「いいえ」でキャンセル'
            )
            reply_text(event.reply_token, message)
            return
    except ValueError:
        pass

    reply_text(event.reply_token, '番号で時間を選択してください。')


def _handle_confirm(event, customer, text, data):
    """予約確定ハンドラ"""
    from booking.services.line_bot_service import reply_text

    if text in _CONFIRM_YES:
        _create_booking(event, customer, data)
    elif text in _CONFIRM_NO:
        _set_state(customer, 'idle')
        reply_text(
            event.reply_token,
            '予約をキャンセルしました。\n「予約」と入力するとやり直せます。',
        )
    else:
        reply_text(event.reply_token, '「はい」か「いいえ」で答えてください。')


def _create_booking(event, customer, data):
    """予約を作成する（confirm から分離）"""
    import datetime as dt
    from zoneinfo import ZoneInfo
    from django.conf import settings as django_settings
    from booking.models import Schedule, Staff, Store
    from booking.models.line_customer import LineCustomer
    from booking.services.line_bot_service import reply_text
    from booking.views import get_time_slots

    staff = Staff.objects.get(id=data['staff_id'])
    store = Store.objects.filter(id=data.get('store_id')).first()
    selected_date = dt.date.fromisoformat(data['date'])

    tz = ZoneInfo(django_settings.TIME_ZONE)
    start = dt.datetime(
        year=selected_date.year,
        month=selected_date.month,
        day=selected_date.day,
        hour=data['hour'],
        minute=data['minute'],
        tzinfo=tz,
    )

    _, _, _, duration = get_time_slots(store or staff.store)
    end = start + dt.timedelta(minutes=duration)

    # 重複チェック
    if Schedule.objects.filter(
        staff=staff, start=start, is_cancelled=False,
    ).exists():
        _set_state(customer, 'idle')
        reply_text(
            event.reply_token,
            '申し訳ございません。その時間は既に予約が入っています。\n'
            '「予約」と入力して再度お試しください。',
        )
        return

    # Schedule作成
    line_user_id = customer.get_line_user_id() or ''
    schedule = Schedule(
        staff=staff,
        store=store or staff.store,
        start=start,
        end=end,
        price=staff.price,
        is_temporary=False,
        booking_channel='line',
        customer_name=customer.display_name or '',
    )
    schedule.set_line_user_id(line_user_id)
    schedule.save()

    # QR生成
    try:
        from booking.services.qr_service import generate_checkin_qr
        qr_content = generate_checkin_qr(str(schedule.reservation_number))
        schedule.checkin_qr.save(qr_content.name, qr_content, save=True)
    except Exception as e:
        logger.warning("QR generation failed for schedule %s: %s", schedule.pk, e)

    # 顧客統計更新（immutable: DB直接更新）
    LineCustomer.objects.filter(pk=customer.pk).update(
        visit_count=customer.visit_count + 1,
        total_spent=customer.total_spent + staff.price,
    )

    _set_state(customer, 'idle')

    local_start = timezone.localtime(schedule.start)
    reply_text(
        event.reply_token,
        f'ご予約ありがとうございます！\n\n'
        f'予約番号: {schedule.reservation_number}\n'
        f'日時: {local_start:%Y/%m/%d %H:%M}\n'
        f'担当: {staff.name}\n'
        f'料金: {staff.price}円\n\n'
        f'キャンセルコード: {schedule.cancel_token}\n'
        f'ご来店をお待ちしております。',
    )

    # スタッフ通知（非同期）
    try:
        from booking.tasks import send_event_notification
        send_event_notification.delay(
            'booking', 'info',
            f'LINE予約: {staff.name} {local_start:%m/%d %H:%M}',
            f'顧客: {customer.display_name or "不明"}',
            '',
        )
    except Exception:
        pass
