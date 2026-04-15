"""エラー報告モデル: ErrorReport"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ErrorReport(models.Model):
    """管理者エラー報告"""
    SEVERITY_CHOICES = [
        ('critical', _('緊急')),
        ('high', _('高')),
        ('medium', _('中')),
        ('low', _('低')),
    ]
    STATUS_CHOICES = [
        ('open', _('未対応')),
        ('in_progress', _('対応中')),
        ('resolved', _('解決済み')),
        ('closed', _('クローズ')),
    ]

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('報告者'),
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reported_errors',
    )
    title = models.CharField(_('エラー概要'), max_length=300)
    description = models.TextField(_('詳細説明'))
    severity = models.CharField(
        _('重要度'), max_length=10, choices=SEVERITY_CHOICES, default='medium',
    )
    status = models.CharField(
        _('ステータス'), max_length=20, choices=STATUS_CHOICES, default='open',
    )
    steps_to_reproduce = models.TextField(_('再現手順'), blank=True, default='')
    screenshot = models.ImageField(
        _('スクリーンショット'), upload_to='error_reports/', blank=True,
    )
    page_url = models.CharField(_('発生ページURL'), max_length=500, blank=True, default='')
    browser_info = models.CharField(_('ブラウザ情報'), max_length=300, blank=True, default='')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_('担当者'),
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_error_reports',
    )
    resolved_at = models.DateTimeField(_('解決日時'), null=True, blank=True)
    resolution_note = models.TextField(_('解決メモ'), blank=True, default='')
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('エラー報告')
        verbose_name_plural = _('エラー報告')
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'
