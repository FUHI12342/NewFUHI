"""シフト関連の共通バリデーション"""
import re

from booking.models import StoreScheduleConfig, StoreClosedDate

MAX_NOTE_LENGTH = 500
_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')


def validate_hour_range(data):
    """start_hour/end_hour のレンジバリデーション。

    Returns:
        tuple: (start_h, end_h, error_message_or_None)
    """
    try:
        start_h = int(data.get('start_hour', 9))
        end_h = int(data.get('end_hour', 17))
    except (ValueError, TypeError):
        return None, None, 'Invalid hour value'
    if not (0 <= start_h <= 23 and 0 <= end_h <= 24 and start_h < end_h):
        return None, None, 'Invalid hour range (0-24, start < end)'
    return start_h, end_h, None


def validate_preference(preference):
    """preference値のバリデーション。不正ならエラーメッセージを返す。"""
    if preference not in ('available', 'preferred', 'unavailable'):
        return 'Invalid preference'
    return None


def validate_min_shift(store, start_h, end_h, preference='available'):
    """最低勤務時間チェック (unavailableはスキップ)。

    Returns:
        tuple: (min_shift_or_None, error_message_or_None)
    """
    if preference == 'unavailable':
        return None, None
    try:
        config = StoreScheduleConfig.objects.get(store=store)
        min_shift = config.min_shift_hours
    except StoreScheduleConfig.DoesNotExist:
        min_shift = 2
    if (end_h - start_h) < min_shift:
        return None, f'最低{min_shift}時間以上のシフトを入力してください。'
    return min_shift, None


def validate_closed_date(store, date):
    """休業日チェック。休業日ならエラーメッセージを返す。"""
    if StoreClosedDate.objects.filter(store=store, date=date).exists():
        return 'この日は休業日のためシフトを入れられません'
    return None


def validate_business_hours(start_h, end_h, open_h, close_h):
    """営業時間内チェック。範囲外ならエラーメッセージを返す。"""
    if start_h < open_h or end_h > close_h or start_h >= end_h:
        return f'営業時間({open_h}:00-{close_h}:00)の範囲で入力してください。'
    return None


def truncate_note(note, max_length=MAX_NOTE_LENGTH):
    """noteフィールドの長さを制限。"""
    if note and len(str(note)) > max_length:
        return str(note)[:max_length]
    return str(note) if note else ''


def validate_color(color):
    """色コードのバリデーション（XSS防止）。不正ならNone、正常なら値を返す。"""
    if color and _COLOR_RE.match(color):
        return color
    return None
