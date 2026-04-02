"""Store theme model for customer-facing page customization."""
from django.db import models
from django.utils.translation import gettext_lazy as _


PRESET_CHOICES = [
    ('default', _('デフォルト')),
    ('elegant', _('エレガント')),
    ('modern', _('モダン')),
    ('natural', _('ナチュラル')),
    ('luxury', _('ラグジュアリー')),
    ('pop', _('ポップ')),
    ('japanese', _('和風')),
    ('custom', _('カスタム')),
]


class StoreTheme(models.Model):
    """店舗ごとの顧客向けページテーマ設定。

    CSS Custom Properties として base.html に注入され、
    Tailwind のカラー定義を上書きする。
    """
    store = models.OneToOneField(
        'Store', on_delete=models.CASCADE,
        related_name='store_theme', verbose_name=_('店舗'),
    )

    # カラー
    primary_color = models.CharField(
        _('プライマリカラー'), max_length=7, default='#8c876c',
        help_text=_('ナビゲーション・ヘッダー背景色'),
    )
    secondary_color = models.CharField(
        _('セカンダリカラー'), max_length=7, default='#f1f0ec',
        help_text=_('サイドバー・カード背景色'),
    )
    accent_color = models.CharField(
        _('アクセントカラー'), max_length=7, default='#b8860b',
        help_text=_('ボタン・リンクのハイライト色'),
    )
    text_color = models.CharField(
        _('テキストカラー'), max_length=7, default='#333333',
        help_text=_('本文テキスト色'),
    )
    header_bg_color = models.CharField(
        _('ヘッダー背景色'), max_length=7, default='#8c876c',
    )
    footer_bg_color = models.CharField(
        _('フッター背景色'), max_length=7, default='#333333',
    )

    # タイポグラフィ
    heading_font = models.CharField(
        _('見出しフォント'), max_length=100,
        default='Hiragino Kaku Gothic Pro',
    )
    body_font = models.CharField(
        _('本文フォント'), max_length=100,
        default='Hiragino Kaku Gothic Pro',
    )

    # ブランディング
    logo = models.ImageField(
        _('ロゴ'), upload_to='themes/logos/', blank=True,
        help_text=_('ヘッダーに表示するロゴ画像'),
    )
    favicon = models.ImageField(
        _('ファビコン'), upload_to='themes/favicons/', blank=True,
    )

    # プリセット
    preset = models.CharField(
        _('テーマプリセット'), max_length=50,
        default='default', choices=PRESET_CHOICES,
    )

    # カスタムCSS（上級者向け）
    custom_css = models.TextField(
        _('カスタムCSS'), blank=True, default='',
        help_text=_('追加CSSを記述できます（上級者向け）'),
    )

    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('店舗テーマ')
        verbose_name_plural = _('店舗テーマ')

    def __str__(self):
        return f'{self.store.name} - {self.get_preset_display()}'

    def apply_preset(self, preset_name):
        """プリセットのカラー値を適用して新しい値を返す（保存はしない）。"""
        from booking.services.theme_presets import THEME_PRESETS
        preset_data = THEME_PRESETS.get(preset_name)
        if not preset_data:
            return self
        for field_name, value in preset_data.items():
            if hasattr(self, field_name):
                setattr(self, field_name, value)
        self.preset = preset_name
        return self
