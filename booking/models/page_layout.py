"""Page layout models for section-based page customization (Phase 2).

Inspired by Shopify Online Store 2.0: JSON-driven section templates
with drag-and-drop reordering and per-section settings.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


PAGE_TYPE_CHOICES = [
    ('home', _('トップページ')),
    ('staff_list', _('スタッフ一覧')),
    ('staff_detail', _('スタッフ詳細')),
    ('shop', _('ショップ')),
    ('notice_list', _('お知らせ一覧')),
]

# Default section order for the home page
DEFAULT_HOME_SECTIONS = [
    {'type': 'hero_banner', 'enabled': True, 'settings': {}},
    {'type': 'page_heading', 'enabled': True, 'settings': {}},
    {'type': 'custom_block_above', 'enabled': True, 'settings': {}},
    {'type': 'entry_cards', 'enabled': True, 'settings': {'columns': 4}},
    {'type': 'custom_block_below', 'enabled': True, 'settings': {}},
    {'type': 'ranking', 'enabled': True, 'settings': {'limit': 5}},
]


class SectionSchema(models.Model):
    """各セクションタイプの設定スキーマ定義。

    管理画面の設定UIを自動生成するためのメタデータ。
    """
    section_type = models.CharField(
        _('セクションタイプ'), max_length=50, unique=True,
    )
    label = models.CharField(_('表示名'), max_length=100)
    description = models.TextField(_('説明'), blank=True, default='')
    icon = models.CharField(
        _('アイコン'), max_length=50, blank=True, default='',
        help_text=_('FontAwesome アイコンクラス名'),
    )
    schema_json = models.JSONField(
        _('設定スキーマ'), default=dict,
        help_text=_('設定UIを自動生成するためのJSON Schema'),
    )
    default_settings = models.JSONField(
        _('デフォルト設定'), default=dict,
    )
    template_name = models.CharField(
        _('テンプレート名'), max_length=200,
        help_text=_('例: booking/sections/hero_banner.html'),
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('セクションスキーマ')
        verbose_name_plural = _('セクションスキーマ')

    def __str__(self):
        return f'{self.label} ({self.section_type})'


class PageLayout(models.Model):
    """店舗×ページ種別ごとのセクション配置設定。

    sections_json は以下の形式:
    [
        {"type": "hero_banner", "enabled": true, "settings": {"autoplay": true}},
        {"type": "entry_cards", "enabled": true, "settings": {"columns": 4}},
        ...
    ]
    """
    store = models.ForeignKey(
        'Store', on_delete=models.CASCADE,
        related_name='page_layouts', verbose_name=_('店舗'),
    )
    page_type = models.CharField(
        _('ページ種別'), max_length=50, choices=PAGE_TYPE_CHOICES,
    )
    sections_json = models.JSONField(
        _('セクション構成'), default=list,
        help_text=_('セクションの並び順・表示/非表示・設定をJSON配列で保持'),
    )
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('ページレイアウト')
        verbose_name_plural = _('ページレイアウト')
        unique_together = ('store', 'page_type')

    def __str__(self):
        return f'{self.store.name} - {self.get_page_type_display()}'

    def get_enabled_sections(self):
        """有効なセクションのリストを返す。template_name をスキーマから解決。"""
        schemas = {
            s.section_type: s
            for s in SectionSchema.objects.all()
        }
        sections = []
        for item in self.sections_json:
            if not item.get('enabled', True):
                continue
            section_type = item.get('type', '')
            schema = schemas.get(section_type)
            template_name = (
                schema.template_name if schema
                else f'booking/sections/{section_type}.html'
            )
            merged_settings = {}
            if schema:
                merged_settings.update(schema.default_settings)
            merged_settings.update(item.get('settings', {}))
            sections.append({
                'type': section_type,
                'template_name': template_name,
                'settings': merged_settings,
                'label': schema.label if schema else section_type,
            })
        return sections
