"""Backup configuration and history models."""
from django.db import models
from django.utils.translation import gettext_lazy as _


class BackupConfig(models.Model):
    """バックアップ設定（シングルトン pk=1）"""
    INTERVAL_CHOICES = [
        ('off', _('無効')),
        ('minute', _('毎分')),
        ('hourly', _('毎時')),
        ('daily', _('毎日')),
    ]

    interval = models.CharField(
        _('バックアップ間隔'), max_length=10,
        choices=INTERVAL_CHOICES, default='off',
    )
    s3_enabled = models.BooleanField(_('S3アップロード'), default=True)
    s3_bucket = models.CharField(
        _('S3バケット名'), max_length=200,
        default='mee-newfuhi-backups',
    )
    local_retention_count = models.IntegerField(
        _('ローカル保持数'), default=30,
        help_text=_('ローカルに保持するバックアップファイルの最大数'),
    )
    s3_retention_days = models.IntegerField(
        _('S3保持日数'), default=90,
        help_text=_('S3上のバックアップを保持する日数'),
    )
    exclude_demo_data = models.BooleanField(
        _('デモデータを除外'), default=True,
        help_text=_('ONにするとis_demo=Trueのレコードをバックアップから除外'),
    )
    line_notify_enabled = models.BooleanField(
        _('LINE通知'), default=True,
        help_text=_('バックアップ完了/失敗時にLINE Notifyで通知'),
    )
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('バックアップ設定')
        verbose_name_plural = _('バックアップ設定')

    def __str__(self):
        return f'バックアップ設定 ({self.get_interval_display()})'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BackupHistory(models.Model):
    """バックアップ実行履歴"""
    STATUS_CHOICES = [
        ('running', _('実行中')),
        ('success', _('成功')),
        ('failed', _('失敗')),
    ]
    TRIGGER_CHOICES = [
        ('scheduled', _('スケジュール')),
        ('manual', _('手動')),
    ]

    backup_file = models.CharField(_('ファイル名'), max_length=500, blank=True, default='')
    file_size_bytes = models.BigIntegerField(_('ファイルサイズ(bytes)'), default=0)
    status = models.CharField(
        _('ステータス'), max_length=10,
        choices=STATUS_CHOICES, default='running',
    )
    trigger = models.CharField(
        _('トリガー'), max_length=10,
        choices=TRIGGER_CHOICES, default='scheduled',
    )
    s3_uploaded = models.BooleanField(_('S3アップロード済み'), default=False)
    s3_key = models.CharField(_('S3キー'), max_length=500, blank=True, default='')
    error_message = models.TextField(_('エラーメッセージ'), blank=True, default='')
    duration_seconds = models.FloatField(_('所要時間(秒)'), default=0)
    started_at = models.DateTimeField(_('開始日時'), auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(_('完了日時'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('バックアップ履歴')
        verbose_name_plural = _('バックアップ履歴')
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status', '-started_at']),
        ]

    def __str__(self):
        return f'{self.backup_file} ({self.get_status_display()})'
