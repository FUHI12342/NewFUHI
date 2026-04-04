"""LINE customer and message log models."""
from django.db import models
from django.utils.translation import gettext_lazy as _


class LineCustomer(models.Model):
    """LINE友だち顧客マスタ"""
    SEGMENT_CHOICES = [
        ('new', _('新規')),
        ('regular', _('リピーター')),
        ('vip', _('VIP')),
        ('dormant', _('休眠')),
    ]

    line_user_hash = models.CharField(
        _('LINEユーザーIDハッシュ'), max_length=64, unique=True, db_index=True,
    )
    line_user_enc = models.TextField(_('LINEユーザーID(暗号化)'))
    display_name = models.CharField(_('表示名'), max_length=255, blank=True, default='')
    is_friend = models.BooleanField(_('友だち'), default=True)
    first_visit_at = models.DateTimeField(_('初回訪問'), auto_now_add=True)
    last_visit_at = models.DateTimeField(_('最終訪問'), auto_now=True)
    visit_count = models.IntegerField(_('来店回数'), default=0)
    total_spent = models.IntegerField(_('累計金額'), default=0)
    tags = models.JSONField(_('タグ'), default=list, blank=True)
    segment = models.CharField(
        _('セグメント'), max_length=20, choices=SEGMENT_CHOICES, default='new',
    )
    store = models.ForeignKey(
        'Store', verbose_name=_('店舗'), null=True, blank=True,
        on_delete=models.SET_NULL, related_name='line_customers',
    )
    blocked_at = models.DateTimeField(_('ブロック日時'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('LINE顧客')
        verbose_name_plural = _('LINE顧客')
        indexes = [
            models.Index(fields=['segment']),
            models.Index(fields=['store', 'segment']),
        ]

    def __str__(self):
        return self.display_name or self.line_user_hash[:8]

    def get_line_user_id(self):
        """暗号文からLINEユーザーIDを復号"""
        if not self.line_user_enc:
            return None
        from .schedule import Schedule
        f = Schedule._get_line_id_fernet()
        try:
            return f.decrypt(self.line_user_enc.encode('utf-8')).decode('utf-8')
        except Exception:
            return None


class LineMessageLog(models.Model):
    """LINE送信ログ"""
    MESSAGE_TYPE_CHOICES = [
        ('reminder', _('リマインダー')),
        ('segment', _('セグメント配信')),
        ('chatbot', _('チャットボット')),
        ('system', _('システム')),
    ]
    STATUS_CHOICES = [
        ('sent', _('送信済み')),
        ('failed', _('失敗')),
    ]

    customer = models.ForeignKey(
        LineCustomer, verbose_name=_('顧客'), on_delete=models.CASCADE,
        null=True, blank=True, related_name='message_logs',
    )
    message_type = models.CharField(_('種別'), max_length=30, choices=MESSAGE_TYPE_CHOICES)
    content_preview = models.CharField(_('内容プレビュー'), max_length=200)
    sent_at = models.DateTimeField(_('送信日時'), auto_now_add=True)
    status = models.CharField(_('ステータス'), max_length=10, choices=STATUS_CHOICES, default='sent')
    error_detail = models.TextField(_('エラー詳細'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('LINE送信ログ')
        verbose_name_plural = _('LINE送信ログ')
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['message_type', '-sent_at']),
        ]

    def __str__(self):
        return f'{self.get_message_type_display()} {self.sent_at:%Y/%m/%d %H:%M}'
