"""分析モデル: BusinessInsight, CustomerFeedback, VisitorCount, VisitorAnalyticsConfig, CostReport"""
import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class BusinessInsight(models.Model):
    """自動生成されるビジネスインサイト"""
    SEVERITY_CHOICES = [
        ('info', _('情報')),
        ('warning', _('注意')),
        ('critical', _('重要')),
    ]
    CATEGORY_CHOICES = [
        ('sales', _('売上')),
        ('inventory', _('在庫')),
        ('staffing', _('スタッフ')),
        ('menu', _('メニュー')),
        ('customer', _('顧客')),
    ]

    store = models.ForeignKey(
        'Store', verbose_name=_('店舗'), on_delete=models.CASCADE,
        related_name='insights', null=True, blank=True,
    )
    category = models.CharField(_('カテゴリ'), max_length=20, choices=CATEGORY_CHOICES)
    severity = models.CharField(_('重要度'), max_length=10, choices=SEVERITY_CHOICES, default='info')
    title = models.CharField(_('タイトル'), max_length=200)
    message = models.TextField(_('メッセージ'))
    data = models.JSONField(_('関連データ'), default=dict, blank=True)
    is_read = models.BooleanField(_('既読'), default=False)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('ビジネスインサイト')
        verbose_name_plural = _('ビジネスインサイト')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['store', 'category', '-created_at']),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'


class CustomerFeedback(models.Model):
    """顧客フィードバック（NPS + 評価 + コメント）"""
    store = models.ForeignKey(
        'Store', verbose_name=_('店舗'), on_delete=models.CASCADE,
        related_name='feedbacks',
    )
    order = models.ForeignKey(
        'Order', verbose_name=_('注文'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='feedbacks',
    )
    customer_hash = models.CharField(_('顧客ハッシュ'), max_length=64, blank=True, default='')
    nps_score = models.IntegerField(
        _('NPS (0-10)'), help_text=_('0=推奨しない 〜 10=強く推奨'),
    )
    food_rating = models.IntegerField(_('料理評価 (1-5)'), default=3)
    service_rating = models.IntegerField(_('サービス評価 (1-5)'), default=3)
    ambiance_rating = models.IntegerField(_('雰囲気評価 (1-5)'), default=3)
    comment = models.TextField(_('コメント'), blank=True, default='')
    SENTIMENT_CHOICES = [
        ('positive', _('ポジティブ')),
        ('neutral', _('ニュートラル')),
        ('negative', _('ネガティブ')),
    ]
    sentiment = models.CharField(
        _('感情分析'), max_length=10, choices=SENTIMENT_CHOICES,
        blank=True, default='',
    )
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('顧客フィードバック')
        verbose_name_plural = _('顧客フィードバック')
        ordering = ['-created_at']

    def __str__(self):
        return f'NPS:{self.nps_score} {self.store.name} ({self.created_at:%Y-%m-%d})'

    @property
    def nps_category(self):
        """NPS category: promoter(9-10), passive(7-8), detractor(0-6)."""
        if self.nps_score >= 9:
            return 'promoter'
        elif self.nps_score >= 7:
            return 'passive'
        return 'detractor'


class VisitorCount(models.Model):
    """時間帯別来客集計"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='visitor_counts')
    date = models.DateField(_('日付'), db_index=True)
    hour = models.IntegerField(_('時間帯'))  # 0-23
    pir_count = models.IntegerField(_('PIR検知数'), default=0)
    estimated_visitors = models.IntegerField(_('推定来客数'), default=0)
    order_count = models.IntegerField(_('注文数'), default=0)
    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('来客数')
        verbose_name_plural = _('来客数')
        unique_together = ('store', 'date', 'hour')
        indexes = [
            models.Index(fields=['store', 'date']),
        ]

    def __str__(self):
        return f'{self.store.name} {self.date} {self.hour}時 来客:{self.estimated_visitors}'


class VisitorAnalyticsConfig(models.Model):
    """店舗ごとの来客分析設定"""
    store = models.OneToOneField('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='visitor_config')
    pir_device = models.ForeignKey('IoTDevice', verbose_name=_('PIRデバイス'), on_delete=models.SET_NULL, null=True, blank=True)
    session_gap_seconds = models.IntegerField(_('セッション間隔(秒)'), default=300,
        help_text=_('この秒数以内の連続検知は同一来客とカウント'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('来客分析設定')
        verbose_name_plural = _('来客分析設定')

    def __str__(self):
        return f'{self.store.name} 来客分析設定'


class CostReport(models.Model):
    """AWSコストレポート"""
    STATUS_CHOICES = [
        ('ok', _('OK')),
        ('warn', _('警告')),
        ('alert', _('アラート')),
    ]
    RESOURCE_TYPE_CHOICES = [
        ('ec2', 'EC2'),
        ('s3', 'S3'),
        ('ebs', 'EBS'),
        ('eip', 'Elastic IP'),
        ('rds', 'RDS'),
        ('total', '合計'),
    ]

    run_id = models.UUIDField(_('実行ID'), default=uuid.uuid4, db_index=True)
    check_name = models.CharField(_('チェック名'), max_length=100)
    resource_type = models.CharField(_('リソース種別'), max_length=10, choices=RESOURCE_TYPE_CHOICES)
    resource_id = models.CharField(_('リソースID'), max_length=200, blank=True, default='')
    status = models.CharField(_('状態'), max_length=10, choices=STATUS_CHOICES)
    estimated_monthly_cost = models.DecimalField(_('推定月額コスト'), max_digits=10, decimal_places=2, default=0)
    detail = models.TextField(_('詳細'), blank=True, default='')
    recommendation = models.TextField(_('推奨事項'), blank=True, default='')
    created_at = models.DateTimeField(_('実行日時'), auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('AWSコストレポート')
        verbose_name_plural = _('AWSコストレポート')
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.check_name} ({self.resource_type})'
