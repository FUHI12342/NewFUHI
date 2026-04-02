"""Custom page models for GrapesJS visual page builder (Phase 3)."""
from django.db import models
from django.utils.translation import gettext_lazy as _


PAGE_TYPE_CHOICES = [
    ('landing', _('ランディングページ')),
    ('campaign', _('キャンペーンページ')),
    ('custom', _('フリーページ')),
]

LAYOUT_CHOICES = [
    ('standard', _('標準')),
    ('full_width', _('フルワイド')),
]

TEMPLATE_CATEGORY_CHOICES = [
    ('salon', _('サロン')),
    ('fortune', _('占いサロン')),
    ('nail', _('ネイルサロン')),
    ('hair', _('ヘアサロン')),
    ('general', _('汎用')),
]


class CustomPage(models.Model):
    """GrapesJS で作成されたカスタムページ。"""
    store = models.ForeignKey(
        'Store', on_delete=models.CASCADE,
        related_name='custom_pages', verbose_name=_('店舗'),
    )
    title = models.CharField(_('ページタイトル'), max_length=200)
    slug = models.SlugField(
        _('URLスラッグ'), max_length=200,
        help_text=_('公開URLに使用されます（例: spring-campaign）'),
    )
    page_type = models.CharField(
        _('ページ種別'), max_length=20, choices=PAGE_TYPE_CHOICES,
        default='custom',
    )
    layout = models.CharField(
        _('レイアウト'), max_length=20, choices=LAYOUT_CHOICES,
        default='standard',
        help_text=_('フルワイドはサイドバーなしのランディングページ向け'),
    )

    # GrapesJS data
    grapesjs_data = models.JSONField(
        _('GrapesJSデータ'), default=dict,
        help_text=_('エディタの状態（コンポーネントツリー・スタイル等）'),
    )
    html_content = models.TextField(
        _('HTML'), blank=True, default='',
        help_text=_('レンダリング済みHTML'),
    )
    css_content = models.TextField(
        _('CSS'), blank=True, default='',
        help_text=_('カスタムCSS'),
    )

    # SEO fields
    meta_title = models.CharField(
        _('メタタイトル'), max_length=70, blank=True, default='',
        help_text=_('検索結果に表示されるタイトル（未設定時はページタイトルを使用）'),
    )
    meta_description = models.TextField(
        _('メタディスクリプション'), max_length=160, blank=True, default='',
        help_text=_('検索結果に表示される説明文（160文字以内推奨）'),
    )
    og_image_url = models.URLField(
        _('OGP画像URL'), max_length=500, blank=True, default='',
        help_text=_('SNSシェア時に表示される画像のURL'),
    )

    is_published = models.BooleanField(_('公開'), default=False)
    published_at = models.DateTimeField(_('公開日時'), null=True, blank=True)

    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('カスタムページ')
        verbose_name_plural = _('カスタムページ')
        unique_together = ('store', 'slug')

    def __str__(self):
        return f'{self.store.name} - {self.title}'

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('booking:custom_page', kwargs={
            'store_id': self.store_id,
            'slug': self.slug,
        })


class PageTemplate(models.Model):
    """GrapesJS ページテンプレート（プリセット or ユーザー作成）。"""
    name = models.CharField(_('テンプレート名'), max_length=100)
    description = models.TextField(_('説明'), blank=True, default='')
    thumbnail = models.ImageField(
        _('サムネイル'), upload_to='page_templates/', blank=True,
    )
    category = models.CharField(
        _('カテゴリ'), max_length=20, choices=TEMPLATE_CATEGORY_CHOICES,
        default='general',
    )

    grapesjs_data = models.JSONField(_('GrapesJSデータ'), default=dict)
    html_content = models.TextField(_('HTML'), blank=True, default='')
    css_content = models.TextField(_('CSS'), blank=True, default='')

    is_system = models.BooleanField(
        _('システムテンプレート'), default=True,
        help_text=_('システム提供テンプレートはユーザーが削除できません'),
    )

    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('ページテンプレート')
        verbose_name_plural = _('ページテンプレート')

    def __str__(self):
        return f'{self.name} ({self.get_category_display()})'


class SavedBlock(models.Model):
    """ユーザーが保存した再利用可能なGrapesJSブロック。"""
    store = models.ForeignKey(
        'Store', on_delete=models.CASCADE,
        related_name='saved_blocks', verbose_name=_('店舗'),
    )
    label = models.CharField(_('ブロック名'), max_length=100)
    category = models.CharField(
        _('カテゴリ'), max_length=50, default='保存済み',
    )
    html_content = models.TextField(_('HTML'))
    css_content = models.TextField(_('CSS'), blank=True, default='')
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('保存済みブロック')
        verbose_name_plural = _('保存済みブロック')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.store.name} - {self.label}'
