"""RAG ナレッジコンテキスト構築サービス"""
import logging
from datetime import date

from django.utils import timezone

logger = logging.getLogger(__name__)


def build_knowledge_context(store, target_date=None):
    """KnowledgeEntry + Staff情報 + 当日シフトを統合テキスト化

    Args:
        store: Store インスタンス
        target_date: 対象日 (None の場合は今日)

    Returns:
        str: AI 生成に渡すコンテキストテキスト
    """
    from booking.models import KnowledgeEntry, Staff
    from booking.models.shifts import ShiftAssignment

    if target_date is None:
        target_date = timezone.localdate()

    sections = []

    # 1. 店舗基本情報
    sections.append(f"【店舗情報】\n店舗名: {store.name}")
    if store.address:
        sections.append(f"住所: {store.address}")
    if store.business_hours:
        sections.append(f"営業時間: {store.business_hours}")
    if store.nearest_station:
        sections.append(f"最寄り駅: {store.nearest_station}")
    if store.description:
        sections.append(f"店舗紹介: {store.description}")

    # 2. ナレッジエントリ
    entries = KnowledgeEntry.objects.filter(
        store=store, is_active=True,
    ).select_related('staff').order_by('category')

    if entries.exists():
        sections.append("\n【ナレッジベース】")
        for entry in entries:
            sections.append(f"[{entry.get_category_display()}] {entry.title}: {entry.content}")

    # 3. 当日のシフト情報
    assignments = ShiftAssignment.objects.filter(
        period__store=store, date=target_date,
    ).select_related('staff').order_by('start_hour')

    if assignments.exists():
        sections.append(f"\n【{target_date.strftime('%Y/%m/%d')} 出勤キャスト】")
        for a in assignments:
            staff = a.staff
            line = f"- {staff.name} ({a.start_hour}:00-{a.end_hour}:00)"
            if staff.introduction:
                intro = staff.introduction[:80]
                line += f" ※{intro}"
            sections.append(line)
    else:
        sections.append(f"\n【{target_date.strftime('%Y/%m/%d')}】出勤キャスト: 未登録")

    return '\n'.join(sections)
