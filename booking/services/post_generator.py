"""コンテンツ生成サービス: テンプレート展開 + ツイート文字数検証"""
import logging
import re
import unicodedata
from datetime import date, timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# X (Twitter) の加重文字数上限
MAX_WEIGHTED_LENGTH = 280

# CJK Unicode範囲 (日本語・中国語・韓国語 = weight 2)
_CJK_RANGES = [
    (0x1100, 0x11FF),    # Hangul Jamo
    (0x2E80, 0x9FFF),    # CJK Radicals ~ CJK Unified Ideographs
    (0xAC00, 0xD7AF),    # Hangul Syllables
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0xFE30, 0xFE4F),    # CJK Compatibility Forms
    (0xFF00, 0xFFEF),    # Halfwidth and Fullwidth Forms
    (0x20000, 0x2FA1F),  # CJK Extension B ~ Kangxi Radicals Supplement
    (0x30000, 0x323AF),  # CJK Extension G+
]


def _is_cjk(char):
    """文字がCJK範囲に含まれるかチェック"""
    cp = ord(char)
    return any(start <= cp <= end for start, end in _CJK_RANGES)


def weighted_length(text):
    """X API v2 の加重文字数を計算。CJK文字 = 2, その他 = 1。"""
    total = 0
    for char in text:
        if _is_cjk(char):
            total += 2
        else:
            total += 1
    return total


def validate_tweet_length(content):
    """ツイートの文字数を検証。(is_valid, weighted_len) を返す。"""
    wlen = weighted_length(content)
    return (wlen <= MAX_WEIGHTED_LENGTH, wlen)


def truncate_to_fit(content, max_weighted=MAX_WEIGHTED_LENGTH, suffix='...'):
    """加重文字数に収まるようにtruncateする。"""
    if weighted_length(content) <= max_weighted:
        return content

    suffix_len = weighted_length(suffix)
    target = max_weighted - suffix_len
    result = []
    current = 0
    for char in content:
        w = 2 if _is_cjk(char) else 1
        if current + w > target:
            break
        result.append(char)
        current += w
    return ''.join(result) + suffix


def flatten_for_x(content):
    """X投稿用に改行をスペースに置換（スパム判定回避）

    連続改行や改行+空白も1スペースに正規化する。
    """
    return re.sub(r'\s*\n\s*', ' ', content).strip()


def append_booking_url(content, store):
    """投稿テキスト末尾に予約URLを追加（X向け）

    改行をスペースに置換してからURLを付与する。

    Args:
        content: 投稿テキスト
        store: Store インスタンス

    Returns:
        URL付き投稿テキスト（1段落+URL）
    """
    content = flatten_for_x(content)
    booking_url = f"https://timebaibai.com/store/{store.id}/staffs/"
    if 'timebaibai.com' in content:
        return content
    return f"{content} {booking_url}"


def render_template(body_template, context):
    """安全な変数展開。未定義変数はそのまま残す。

    利用可能変数: {store_name}, {date}, {staff_list}, {business_hours}, {month}
    """
    safe_context = {k: str(v) for k, v in context.items()}

    def _replace(match):
        key = match.group(1)
        return safe_context.get(key, match.group(0))

    return re.sub(r'\{(\w+)\}', _replace, body_template)


def _format_staff_list(assignments):
    """ShiftAssignment queryset からスタッフ名リストを文字列化"""
    names = []
    for a in assignments.select_related('staff'):
        time_str = f"{a.start_hour}:00-{a.end_hour}:00"
        names.append(f"{a.staff.name}({time_str})")
    return '、'.join(names) if names else '未定'


def build_shift_publish_content(store, period, template):
    """シフト公開時の投稿コンテンツを生成"""
    from booking.models import ShiftAssignment

    month_str = period.year_month.strftime('%Y年%m月')
    assignments = ShiftAssignment.objects.filter(
        period=period,
    ).select_related('staff').order_by('date', 'start_hour')

    staff_names = sorted(set(
        a.staff.name for a in assignments
    ))
    staff_list = '、'.join(staff_names) if staff_names else '未定'

    context = {
        'store_name': store.name,
        'month': month_str,
        'staff_list': staff_list,
        'date': month_str,
    }
    content = render_template(template.body_template, context)
    return truncate_to_fit(content)


def build_daily_staff_content(store, target_date, template):
    """本日のスタッフ投稿コンテンツを生成"""
    from booking.models import ShiftAssignment

    assignments = ShiftAssignment.objects.filter(
        period__store=store,
        date=target_date,
    ).select_related('staff').order_by('start_hour')

    staff_list = _format_staff_list(assignments)
    date_str = target_date.strftime('%m/%d(%a)')

    context = {
        'store_name': store.name,
        'date': date_str,
        'staff_list': staff_list,
    }
    content = render_template(template.body_template, context)
    return truncate_to_fit(content)


def build_weekly_schedule_content(store, week_start, template):
    """週間スケジュール投稿コンテンツを生成"""
    from booking.models import ShiftAssignment

    week_end = week_start + timedelta(days=6)
    assignments = ShiftAssignment.objects.filter(
        period__store=store,
        date__gte=week_start,
        date__lte=week_end,
    ).select_related('staff').order_by('date', 'start_hour')

    # 日別にスタッフ名を集約
    daily = {}
    for a in assignments:
        day_key = a.date.strftime('%m/%d(%a)')
        if day_key not in daily:
            daily[day_key] = []
        daily[day_key].append(a.staff.name)

    lines = []
    for day_key, names in daily.items():
        unique_names = sorted(set(names))
        lines.append(f"{day_key}: {'、'.join(unique_names)}")
    staff_list = '\n'.join(lines) if lines else '未定'

    period_str = f"{week_start.strftime('%m/%d')}~{week_end.strftime('%m/%d')}"
    context = {
        'store_name': store.name,
        'date': period_str,
        'staff_list': staff_list,
        'month': week_start.strftime('%Y年%m月'),
    }
    content = render_template(template.body_template, context)
    return truncate_to_fit(content)


def build_content(trigger_type, store, context_data, template):
    """トリガー種別に応じたコンテンツを生成するディスパッチ関数"""
    if trigger_type == 'shift_publish':
        from booking.models import ShiftPeriod
        period_id = context_data.get('period_id')
        period = ShiftPeriod.objects.select_related('store').get(id=period_id)
        return build_shift_publish_content(store, period, template)

    elif trigger_type == 'daily_staff':
        target_date = date.today()
        return build_daily_staff_content(store, target_date, template)

    elif trigger_type == 'weekly_schedule':
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        return build_weekly_schedule_content(store, week_start, template)

    elif trigger_type == 'manual':
        content = context_data.get('content', '')
        return truncate_to_fit(content) if content else ''

    else:
        logger.warning("Unknown trigger_type: %s", trigger_type)
        return ''
