"""ブラウザ自動投稿モデル: BrowserSession, BrowserPostLog"""
from django.db import models
from django.utils.translation import gettext_lazy as _


BROWSER_PLATFORM_CHOICES = [
    ('x', 'X (Twitter)'),
    ('instagram', 'Instagram'),
    ('gbp', 'Google Business Profile'),
]

SESSION_STATUS_CHOICES = [
    ('active', _('有効')),
    ('expired', _('期限切れ')),
    ('setup_required', _('セットアップ必要')),
]


class BrowserSession(models.Model):
    """ブラウザセッション管理（プラットフォームごとのプロファイル）"""

    store = models.ForeignKey(
        'booking.Store', on_delete=models.CASCADE,
        related_name='browser_sessions', verbose_name=_('店舗'),
    )
    platform = models.CharField(
        max_length=20, choices=BROWSER_PLATFORM_CHOICES,
        verbose_name=_('プラットフォーム'),
    )
    profile_dir = models.CharField(
        max_length=500, verbose_name=_('プロファイルディレクトリ'),
        help_text=_('MEDIA_ROOT/browser_profiles/<store>/<platform>/'),
    )
    status = models.CharField(
        max_length=20, choices=SESSION_STATUS_CHOICES,
        default='setup_required', verbose_name=_('状態'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'social_browser'
        unique_together = ('store', 'platform')
        verbose_name = _('ブラウザセッション')
        verbose_name_plural = _('ブラウザセッション')

    def __str__(self):
        return f"{self.store.name} - {self.get_platform_display()} ({self.get_status_display()})"


class BrowserPostLog(models.Model):
    """ブラウザ投稿ログ"""

    session = models.ForeignKey(
        BrowserSession, on_delete=models.CASCADE,
        related_name='post_logs', verbose_name=_('セッション'),
    )
    draft_post = models.ForeignKey(
        'booking.DraftPost', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='browser_post_logs',
        verbose_name=_('元下書き'),
    )
    content = models.TextField(verbose_name=_('投稿内容'))
    success = models.BooleanField(default=False, verbose_name=_('成功'))
    error_message = models.TextField(blank=True, verbose_name=_('エラーメッセージ'))
    screenshot = models.ImageField(
        upload_to='browser_screenshots/', blank=True,
        verbose_name=_('スクリーンショット'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'social_browser'
        ordering = ['-created_at']
        verbose_name = _('ブラウザ投稿ログ')
        verbose_name_plural = _('ブラウザ投稿ログ')

    def __str__(self):
        status = '成功' if self.success else '失敗'
        return f"{self.session} [{status}] {self.created_at}"
