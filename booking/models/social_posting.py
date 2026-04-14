"""SNS自動投稿モデル: SocialAccount, PostTemplate, PostHistory, KnowledgeEntry, DraftPost"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from booking.fields import EncryptedCharField


PLATFORM_CHOICES = [
    ('x', 'X (Twitter)'),
    ('instagram', 'Instagram'),
    ('gbp', 'Google Business Profile'),
    ('tiktok', 'TikTok'),
]

TRIGGER_CHOICES = [
    ('shift_publish', _('シフト公開時')),
    ('daily_staff', _('本日のスタッフ')),
    ('weekly_schedule', _('週間スケジュール')),
    ('manual', _('手動投稿')),
]

POST_STATUS_CHOICES = [
    ('pending', _('投稿待ち')),
    ('posted', _('投稿済み')),
    ('failed', _('失敗')),
    ('skipped', _('スキップ（制限超過等）')),
]


class SocialAccount(models.Model):
    """店舗ごとのX OAuth認証情報（暗号化トークン保存）"""

    store = models.ForeignKey(
        'booking.Store',
        on_delete=models.CASCADE,
        related_name='social_accounts',
        verbose_name=_('店舗'),
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default='x',
        verbose_name=_('プラットフォーム'),
    )
    account_name = models.CharField(
        max_length=100,
        verbose_name=_('アカウント名'),
        help_text=_('@username'),
    )
    access_token = EncryptedCharField(
        max_length=500,
        blank=True,
        verbose_name=_('アクセストークン'),
    )
    refresh_token = EncryptedCharField(
        max_length=500,
        blank=True,
        verbose_name=_('リフレッシュトークン'),
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('トークン有効期限'),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('有効'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        unique_together = ('store', 'platform')
        verbose_name = _('SNSアカウント')
        verbose_name_plural = _('SNSアカウント')

    def __str__(self):
        return f"{self.store.name} - {self.get_platform_display()} (@{self.account_name})"


class PostTemplate(models.Model):
    """トリガー種別ごとの投稿テンプレート"""

    store = models.ForeignKey(
        'booking.Store',
        on_delete=models.CASCADE,
        related_name='post_templates',
        verbose_name=_('店舗'),
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default='x',
        verbose_name=_('プラットフォーム'),
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        verbose_name=_('トリガー種別'),
    )
    body_template = models.TextField(
        verbose_name=_('テンプレート本文'),
        help_text=_(
            '利用可能な変数: {store_name}, {date}, {staff_list}, '
            '{business_hours}, {month}'
        ),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_('有効'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        unique_together = ('store', 'platform', 'trigger_type')
        verbose_name = _('投稿テンプレート')
        verbose_name_plural = _('投稿テンプレート')

    def __str__(self):
        return f"{self.store.name} - {self.get_trigger_type_display()}"


class PostHistory(models.Model):
    """投稿履歴（不変監査ログ）"""

    store = models.ForeignKey(
        'booking.Store',
        on_delete=models.CASCADE,
        related_name='post_histories',
        verbose_name=_('店舗'),
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        verbose_name=_('プラットフォーム'),
    )
    trigger_type = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        verbose_name=_('トリガー種別'),
    )
    content = models.TextField(
        verbose_name=_('投稿内容'),
    )
    status = models.CharField(
        max_length=10,
        choices=POST_STATUS_CHOICES,
        default='pending',
        verbose_name=_('ステータス'),
    )
    external_post_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_('外部投稿ID'),
        help_text=_('冪等性チェック用'),
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_('エラーメッセージ'),
    )
    retry_count = models.IntegerField(
        default=0,
        verbose_name=_('リトライ回数'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    posted_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_('投稿日時'),
    )

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']
        verbose_name = _('投稿履歴')
        verbose_name_plural = _('投稿履歴')

    def __str__(self):
        return f"{self.store.name} - {self.get_trigger_type_display()} ({self.get_status_display()})"


# ==============================
# RAG ナレッジベース
# ==============================

KNOWLEDGE_CATEGORY_CHOICES = [
    ('cast_profile', _('キャストプロフィール')),
    ('store_info', _('店舗情報')),
    ('service_info', _('サービス情報')),
    ('campaign', _('キャンペーン')),
    ('custom', _('カスタム')),
]


class KnowledgeEntry(models.Model):
    """SNS投稿生成用のナレッジベースエントリ"""

    store = models.ForeignKey(
        'booking.Store', on_delete=models.CASCADE,
        related_name='knowledge_entries', verbose_name=_('店舗'),
    )
    category = models.CharField(
        max_length=20, choices=KNOWLEDGE_CATEGORY_CHOICES,
        verbose_name=_('カテゴリ'),
    )
    staff = models.ForeignKey(
        'booking.Staff', on_delete=models.CASCADE,
        null=True, blank=True, related_name='knowledge_entries',
        verbose_name=_('スタッフ'),
        help_text=_('cast_profile の場合のみ指定'),
    )
    title = models.CharField(max_length=200, verbose_name=_('タイトル'))
    content = models.TextField(verbose_name=_('内容'), help_text=_('AI生成の参照情報'))
    is_active = models.BooleanField(default=True, verbose_name=_('有効'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('SNSナレッジ')
        verbose_name_plural = _('SNSナレッジ')
        ordering = ['store', 'category', 'title']

    def __str__(self):
        return f"{self.store.name} - {self.get_category_display()}: {self.title}"


# ==============================
# AI 下書き
# ==============================

DRAFT_STATUS_CHOICES = [
    ('generated', _('AI生成済み')),
    ('reviewed', _('レビュー中')),
    ('approved', _('承認済み')),
    ('rejected', _('却下')),
    ('posted', _('投稿済み')),
    ('scheduled', _('予約投稿')),
]


class DraftPost(models.Model):
    """AI生成SNS下書き — 編集・承認・投稿管理"""

    store = models.ForeignKey(
        'booking.Store', on_delete=models.CASCADE,
        related_name='draft_posts', verbose_name=_('店舗'),
    )
    content = models.TextField(verbose_name=_('投稿内容'), help_text=_('編集可能'))
    ai_generated_content = models.TextField(
        blank=True, verbose_name=_('AI生成原文'),
        help_text=_('編集前の原文（監査用）'),
    )
    platforms = models.JSONField(
        default=list, verbose_name=_('投稿先プラットフォーム'),
        help_text=_('例: ["x", "instagram", "gbp"]'),
    )
    status = models.CharField(
        max_length=20, choices=DRAFT_STATUS_CHOICES,
        default='generated', verbose_name=_('ステータス'),
    )
    target_date = models.DateField(
        null=True, blank=True, verbose_name=_('対象日'),
        help_text=_('出勤情報の対象日'),
    )
    scheduled_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('予約投稿日時'),
    )
    quality_score = models.FloatField(
        null=True, blank=True, verbose_name=_('品質スコア'),
        help_text=_('LLM Judge スコア (0.0-1.0)'),
    )
    quality_feedback = models.TextField(
        blank=True, verbose_name=_('品質フィードバック'),
    )
    image = models.ImageField(
        upload_to='draft_images/', blank=True, null=True,
        verbose_name=_('画像'),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name=_('作成者'),
    )
    posted_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_('投稿日時'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['-created_at']
        verbose_name = _('SNS下書き')
        verbose_name_plural = _('SNS下書き')

    def __str__(self):
        content = self.content or ''
        short = content[:40] + '...' if len(content) > 40 else content
        return f"{self.store.name} [{self.get_status_display()}] {short}"
