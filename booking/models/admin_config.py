"""管理設定モデル: DashboardLayout, AdminTheme, SiteSettings, AdminSidebarSettings, AdminMenuConfig"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# ==============================
# ダッシュボードレイアウト
# ==============================

DEFAULT_DASHBOARD_LAYOUT = [
    {"id": "reservations_kpi", "x": 0, "y": 0, "w": 12, "h": 2},
    {"id": "reservation_chart", "x": 0, "y": 2, "w": 12, "h": 4},
    {"id": "sales_trend", "x": 0, "y": 6, "w": 6, "h": 4},
    {"id": "top_products", "x": 6, "y": 6, "w": 6, "h": 4},
    {"id": "staff_performance", "x": 0, "y": 10, "w": 12, "h": 4},
]


LANGUAGE_CHOICES = [
    ('', _('自動（ブラウザ設定に従う）')),
    ('ja', '日本語'),
    ('zh-hant', '繁體中文'),
    ('en', 'English'),
    ('ko', '한국어'),
    ('es', 'Español'),
    ('pt', 'Português'),
    ('zh-hans', '简体中文'),
]


class DashboardLayout(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='dashboard_layout',
    )
    layout_json = models.JSONField(_('レイアウトJSON'), default=list)
    dark_mode = models.BooleanField(_('ダークモード'), default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('ダッシュボードレイアウト')
        verbose_name_plural = _('ダッシュボードレイアウト')

    def __str__(self):
        return f'DashboardLayout({self.user.username})'


class AdminTheme(models.Model):
    """管理画面UIカスタムテーマ"""
    store = models.OneToOneField('Store', on_delete=models.CASCADE, related_name='admin_theme')
    primary_color = models.CharField(_('メインカラー'), max_length=7, default='#8c876c')
    secondary_color = models.CharField(_('サブカラー'), max_length=7, default='#f1f0ec')
    header_image = models.ImageField(_('ヘッダー画像'), upload_to='admin_themes/', blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('管理画面テーマ')
        verbose_name_plural = _('管理画面テーマ')

    def __str__(self):
        return f"{self.store.name} テーマ"


class SiteSettings(models.Model):
    """サイト全体の設定 (シングルトン)"""
    site_name = models.CharField(_('サイト名'), max_length=200, default='占いサロンチャンス')

    # 表示言語固定
    forced_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default='',
        blank=True,
        verbose_name=_('表示言語固定'),
        help_text=_('設定すると全ユーザーの表示言語をこの言語に固定します。空欄＝ブラウザ設定に従う'),
    )

    # ホームページカードON/OFF
    show_card_store = models.BooleanField(_('店舗カード表示'), default=True)
    show_card_fortune_teller = models.BooleanField(_('占い師カード表示'), default=True)
    show_card_calendar = models.BooleanField(_('カレンダーカード表示'), default=True)
    show_card_shop = models.BooleanField(_('ショップカード表示'), default=True)

    # サイドバーON/OFF
    show_sidebar_notice = models.BooleanField(_('お知らせ表示'), default=True)
    show_sidebar_company = models.BooleanField(_('運営会社表示'), default=True)
    show_sidebar_media = models.BooleanField(_('メディア掲載表示'), default=True)
    show_sidebar_social = models.BooleanField(_('SNSフィード表示'), default=False)

    # SNS連携URL
    twitter_url = models.URLField(_('X(Twitter) URL'), blank=True, default='',
        help_text=_('例: https://x.com/youraccount'))
    instagram_url = models.URLField(_('Instagram URL'), blank=True, default='',
        help_text=_('例: https://www.instagram.com/youraccount'))
    threads_url = models.URLField(_('Threads URL'), blank=True, default='',
        help_text=_('例: https://www.threads.com/@youraccount'))
    tiktok_url = models.URLField(_('TikTok URL'), blank=True, default='',
        help_text=_('例: https://www.tiktok.com/@youraccount'))

    # ヒーローバナー
    show_hero_banner = models.BooleanField(_('ヒーローバナー表示'), default=True)

    # 予約ランキング
    show_ranking = models.BooleanField(_('予約ランキング表示'), default=True)
    ranking_limit = models.IntegerField(_('ランキング表示件数'), default=5)

    # 外部リンク
    show_sidebar_external_links = models.BooleanField(_('外部リンク表示'), default=True)

    # サイドバー並び順（JSON: セクションキーのリスト）
    sidebar_order = models.JSONField(
        _('サイドバー並び順'), blank=True, default=list,
        help_text=_('セクションの表示順序。例: ["notice","sns","media","external_links","company"]'),
    )

    # Instagram埋め込みHTML
    instagram_embed_html = models.TextField(_('Instagram埋め込みHTML'), blank=True, default='',
        help_text=_('Instagramの投稿埋め込みHTMLを貼り付けてください'))

    # スタッフ呼称設定
    staff_label = models.CharField(_('スタッフの呼称'), max_length=50, default='キャスト',
        help_text=_('管理画面・フロントで「占い師」「スタッフ」の代わりに表示する名称（例: キャスト、セラピスト）'))
    staff_label_i18n = models.JSONField(_('スタッフ呼称（多言語）'), default=dict, blank=True,
        help_text=_('言語コードをキーとした翻訳辞書。例: {"en": "Cast", "ko": "캐스트", "zh-hant": "演員"}。未設定の言語はデフォルト呼称を使用。'))

    # 料金ラベル設定
    price_label = models.CharField(_('料金ラベル'), max_length=50, default='鑑定料',
        help_text=_('スタッフ一覧で表示する料金の名称（例: 鑑定料、指名料、施術料）'))

    # AIチャットウィジェット
    show_ai_chat = models.BooleanField(_('AIアシスタント表示'), default=False,
        help_text=_('フロントページにAIアシスタントチャットを表示するかどうか'))

    # デモモード
    demo_mode_enabled = models.BooleanField(_('デモモード'), default=False,
        help_text=_('ONにするとデモデータもダッシュボードに表示します。OFFで実データのみ表示'))

    # LINE機能フィーチャーフラグ
    line_chatbot_enabled = models.BooleanField(_('LINEチャットボット'), default=False,
        help_text=_('LINEからのチャットボット予約を有効化'))
    line_reminder_enabled = models.BooleanField(_('LINEリマインダー'), default=False,
        help_text=_('予約前日・当日のLINEリマインダー送信を有効化'))
    line_segment_enabled = models.BooleanField(_('LINEセグメント配信'), default=False,
        help_text=_('顧客セグメント別のLINE配信機能を有効化'))

    # SNS自動投稿フィーチャーフラグ
    sns_daily_staff_enabled = models.BooleanField(_('毎日スタッフ投稿'), default=True,
        help_text=_('毎日09:30にスタッフ情報を自動投稿'))
    sns_weekly_schedule_enabled = models.BooleanField(_('週間スケジュール投稿'), default=True,
        help_text=_('毎週月曜10:00に週間スケジュールを自動投稿'))
    sns_drafts_generation_enabled = models.BooleanField(_('下書き自動生成'), default=True,
        help_text=_('毎日08:00にAI下書きを自動生成'))
    sns_scheduled_posts_enabled = models.BooleanField(_('予約投稿実行'), default=True,
        help_text=_('予約投稿を5分ごとにチェック・実行'))

    # 管理画面サイドバー機能ON/OFF
    show_admin_reservation = models.BooleanField(_('予約管理を表示'), default=True,
        help_text=_('管理サイドバーに「予約管理」を表示するかどうか'))
    show_admin_shift = models.BooleanField(_('シフト管理を表示'), default=True,
        help_text=_('管理サイドバーに「シフト」を表示するかどうか'))
    show_admin_staff_manage = models.BooleanField(_('従業員管理を表示'), default=True,
        help_text=_('管理サイドバーに「従業員管理」を表示するかどうか'))
    show_admin_menu_manage = models.BooleanField(_('メニュー管理を表示'), default=True,
        help_text=_('管理サイドバーに「メニュー管理」を表示するかどうか'))
    show_admin_inventory = models.BooleanField(_('在庫管理を表示'), default=True,
        help_text=_('管理サイドバーに「在庫管理」を表示するかどうか'))
    show_admin_order = models.BooleanField(_('注文管理を表示'), default=True,
        help_text=_('管理サイドバーに「注文管理」を表示するかどうか'))
    show_admin_pos = models.BooleanField(_('レジ（POS）を表示'), default=True,
        help_text=_('管理サイドバーに「レジ（POS）」を表示するかどうか'))
    show_admin_kitchen = models.BooleanField(_('キッチンディスプレイを表示'), default=True,
        help_text=_('管理サイドバーに「キッチンディスプレイ」を表示するかどうか'))
    show_admin_ec_shop = models.BooleanField(_('オンラインショップを表示'), default=True,
        help_text=_('管理サイドバーに「オンラインショップ」を表示するかどうか'))
    show_admin_table_order = models.BooleanField(_('店舗管理を表示'), default=True,
        help_text=_('管理サイドバーに「店舗管理」を表示するかどうか'))
    show_admin_iot = models.BooleanField(_('IoT管理を表示'), default=True,
        help_text=_('管理サイドバーに「IoT管理」を表示するかどうか'))
    show_admin_pin_clock = models.BooleanField(_('タイムカードを表示'), default=True,
        help_text=_('管理サイドバーに「タイムカード打刻」を表示するかどうか'))
    show_admin_page_settings = models.BooleanField(_('ページ設定を表示'), default=True,
        help_text=_('管理サイドバーに「メインページ設定」を表示するかどうか'))
    show_admin_system = models.BooleanField(_('システムを表示'), default=True,
        help_text=_('管理サイドバーに「システム」を表示するかどうか'))
    show_admin_sns_posting = models.BooleanField(_('SNS投稿を表示'), default=True,
        help_text=_('管理サイドバーに「SNS自動投稿」を表示するかどうか'))
    show_admin_security = models.BooleanField(_('セキュリティを表示'), default=True,
        help_text=_('管理サイドバーに「セキュリティ」を表示するかどうか'))
    show_admin_user_account = models.BooleanField(_('ユーザー管理を表示'), default=True,
        help_text=_('管理サイドバーに「ユーザーアカウント管理」を表示するかどうか'))

    # メンテナンスモード
    maintenance_mode = models.BooleanField(
        _('メンテナンスモード'), default=False,
        help_text=_('ONにするとログイン済みスタッフ以外にメンテナンス画面を表示'),
    )
    maintenance_message = models.TextField(
        _('メンテナンスメッセージ'), blank=True, default='',
        help_text=_('カスタムメッセージ（空の場合はデフォルト表示）'),
    )

    # 外部埋め込みグローバル設定
    embed_enabled = models.BooleanField(
        _('外部埋め込みを有効化'), default=False,
        help_text=_('ONにするとWordPress等からのiframe埋め込みが利用可能になります'),
    )

    # 無料予約モード
    free_booking_mode = models.BooleanField(
        _('無料予約モード'), default=False,
        help_text=_('ONにすると全予約が決済スキップ・即確定になります'),
    )

    # 法定ページ（HTML編集可能）
    privacy_policy_html = models.TextField(_('プライバシーポリシー'), blank=True, default='',
        help_text=_('HTMLで記述。空の場合はデフォルトテンプレートが表示されます。'))
    tokushoho_html = models.TextField(_('特定商取引法に基づく表記'), blank=True, default='',
        help_text=_('HTMLで記述。空の場合はデフォルトテンプレートが表示されます。'))

    # 通知設定
    notification_emails = models.TextField(
        _('通知先メールアドレス'), blank=True, default='',
        help_text=_('カンマ区切りで複数アドレス指定可'),
    )
    notification_enabled = models.BooleanField(_('メール通知を有効化'), default=False)
    notification_rate_limit = models.IntegerField(
        _('通知レート制限'), default=10,
        help_text=_('1時間あたりの最大通知送信数'),
    )
    shanon_notification_enabled = models.BooleanField(_('SHANON通知を有効化'), default=False)
    shanon_api_url = models.URLField(
        _('SHANON API URL'), blank=True, default='http://localhost:8765',
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('メインサイト設定')
        verbose_name_plural = _('メインサイト設定')

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        from booking.services.html_sanitizer import (
            sanitize_rich_text, sanitize_url, sanitize_embed,
        )
        if self.privacy_policy_html:
            self.privacy_policy_html = sanitize_rich_text(self.privacy_policy_html)
        if self.tokushoho_html:
            self.tokushoho_html = sanitize_rich_text(self.tokushoho_html)
        if hasattr(self, 'instagram_embed_html') and self.instagram_embed_html:
            self.instagram_embed_html = sanitize_embed(self.instagram_embed_html)
        if self.twitter_url:
            self.twitter_url = sanitize_url(self.twitter_url)
        if self.instagram_url:
            self.instagram_url = sanitize_url(self.instagram_url)
        if self.threads_url:
            self.threads_url = sanitize_url(self.threads_url)
        if self.tiktok_url:
            self.tiktok_url = sanitize_url(self.tiktok_url)
        super().save(*args, **kwargs)
        # Invalidate cache on save
        from django.core.cache import cache
        cache.delete('site_settings_singleton')

    @classmethod
    def load(cls):
        from django.core.cache import cache
        obj = cache.get('site_settings_singleton')
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set('site_settings_singleton', obj, 60)
        return obj


class AdminSidebarSettings(SiteSettings):
    """管理画面サイドバー設定 — SiteSettings のプロキシモデル（システム管理用）"""
    class Meta:
        proxy = True
        app_label = 'booking'
        verbose_name = _('管理サイドバー設定')
        verbose_name_plural = _('管理サイドバー設定')


class AdminMenuConfig(models.Model):
    """ロールごとの管理画面サイドバー表示メニュー設定"""
    ROLE_CHOICES = [
        ('developer', _('開発者')),
        ('owner', _('オーナー')),
        ('manager', _('店長')),
        ('staff', _('スタッフ')),
    ]
    role = models.CharField(_('ロール'), max_length=20, choices=ROLE_CHOICES, unique=True,
        help_text=_('superuserは常に全モデルを表示するため設定不要'))
    allowed_models = models.JSONField(_('表示許可モデル'), default=list)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)
    updated_by = models.ForeignKey('auth.User', verbose_name=_('更新者'),
        on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('権限設定')
        verbose_name_plural = _('権限設定')

    def __str__(self):
        return f'{self.get_role_display()} メニュー設定'
