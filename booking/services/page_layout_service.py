"""Service for resolving page sections based on PageLayout or defaults."""
from booking.models.page_layout import DEFAULT_HOME_SECTIONS


# Section type -> template path mapping (fallback when no SectionSchema exists)
SECTION_TEMPLATES = {
    'hero_banner': 'booking/sections/hero_banner.html',
    'page_heading': 'booking/sections/page_heading.html',
    'entry_cards': 'booking/sections/entry_cards.html',
    'custom_block_above': 'booking/sections/custom_block_above.html',
    'custom_block_below': 'booking/sections/custom_block_below.html',
    'ranking': 'booking/sections/ranking.html',
}


def get_page_sections(store, page_type='home'):
    """指定された店舗・ページタイプのセクションリストを返す。

    PageLayout が存在すればそれを使用し、なければデフォルトを返す。
    PageLayout が存在しない場合でも全く同じ表示になるため、安全。
    """
    from booking.models import PageLayout

    sections_data = None
    if store:
        try:
            layout = PageLayout.objects.get(store=store, page_type=page_type)
            sections_data = layout.sections_json
        except PageLayout.DoesNotExist:
            pass

    if sections_data is None:
        sections_data = _get_default_sections(page_type)

    return _resolve_sections(sections_data)


def _get_default_sections(page_type):
    """ページタイプごとのデフォルトセクション構成を返す。"""
    if page_type == 'home':
        return DEFAULT_HOME_SECTIONS
    return []


def _resolve_sections(sections_data):
    """JSON セクションデータを template_name 付きの辞書リストに変換。"""
    resolved = []
    for item in sections_data:
        if not item.get('enabled', True):
            continue
        section_type = item.get('type', '')
        template_name = SECTION_TEMPLATES.get(
            section_type,
            f'booking/sections/{section_type}.html',
        )
        resolved.append({
            'type': section_type,
            'template_name': template_name,
            'settings': item.get('settings', {}),
            'enabled': True,
        })
    return resolved
