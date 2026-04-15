"""セキュリティモデル: SecurityAudit, SecurityLog"""
import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SecurityAudit(models.Model):
    """セキュリティ監査結果"""
    SEVERITY_CHOICES = [
        ('critical', _('重大')),
        ('high', _('高')),
        ('medium', _('中')),
        ('low', _('低')),
        ('info', _('情報')),
        ('pass', _('合格')),
    ]
    STATUS_CHOICES = [
        ('fail', _('不合格')),
        ('warn', _('警告')),
        ('pass', _('合格')),
    ]
    CATEGORY_CHOICES = [
        ('django_settings', _('Django設定')),
        ('credentials', _('認証情報')),
        ('endpoints', _('エンドポイント')),
        ('infrastructure', _('インフラ')),
        ('dependencies', _('依存関係')),
    ]

    run_id = models.UUIDField(_('実行ID'), default=uuid.uuid4, db_index=True)
    check_name = models.CharField(_('チェック名'), max_length=100)
    category = models.CharField(_('カテゴリ'), max_length=30, choices=CATEGORY_CHOICES)
    severity = models.CharField(_('重大度'), max_length=10, choices=SEVERITY_CHOICES)
    status = models.CharField(_('結果'), max_length=10, choices=STATUS_CHOICES)
    message = models.TextField(_('メッセージ'))
    recommendation = models.TextField(_('推奨事項'), blank=True, default='')
    created_at = models.DateTimeField(_('実行日時'), auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('セキュリティ監査')
        verbose_name_plural = _('セキュリティ監査')
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.check_name}: {self.get_status_display()}'


class SecurityLog(models.Model):
    """セキュリティイベントログ"""
    EVENT_TYPE_CHOICES = [
        ('login_success', _('ログイン成功')),
        ('login_fail', _('ログイン失敗')),
        ('api_auth_fail', _('API認証失敗')),
        ('permission_denied', _('権限拒否')),
        ('suspicious_request', _('不審なリクエスト')),
        ('admin_action', _('管理操作')),
        ('maintenance_on', _('メンテナンス開始')),
        ('maintenance_off', _('メンテナンス終了')),
        ('server_error', _('サーバーエラー')),
    ]
    SEVERITY_CHOICES = [
        ('critical', _('緊急')),
        ('warning', _('警告')),
        ('info', _('情報')),
    ]

    event_type = models.CharField(_('イベント種別'), max_length=30, choices=EVENT_TYPE_CHOICES, db_index=True)
    severity = models.CharField(_('重要度'), max_length=10, choices=SEVERITY_CHOICES, default='info')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('ユーザー'),
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    username = models.CharField(_('ユーザー名'), max_length=150, blank=True, default='')
    ip_address = models.GenericIPAddressField(_('IPアドレス'), null=True, blank=True)
    user_agent = models.TextField(_('User-Agent'), blank=True, default='')
    path = models.CharField(_('パス'), max_length=500, blank=True, default='')
    method = models.CharField(_('メソッド'), max_length=10, blank=True, default='')
    detail = models.TextField(_('詳細'), blank=True, default='')
    created_at = models.DateTimeField(_('発生日時'), auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('セキュリティログ')
        verbose_name_plural = _('セキュリティログ')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.get_event_type_display()} - {self.username} ({self.ip_address})'
