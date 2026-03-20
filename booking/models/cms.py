"""CMS models: Notice, Media, SiteSettings, HeroBanner, BannerAd, Security, etc."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

import uuid
import textwrap
from decimal import Decimal
from newspaper import Article


class Company(models.Model):
    name = models.CharField(_('会社名'), max_length=255)
    address = models.CharField(_('住所'), max_length=255)
    tel = models.CharField(_('電話番号'), max_length=20, default='000-0000-0000')

    class Meta:
        app_label = 'booking'
        verbose_name = _('運営会社情報')
        verbose_name_plural = _('運営会社情報')

    def __str__(self):
        return self.name


class Notice(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=200, unique=True, blank=True,
        help_text=_('URLスラッグ（空欄なら自動生成）'),
    )
    link = models.URLField(blank=True, default='')
    content = models.TextField(default='', help_text=_('HTML形式で記述できます'))
    is_published = models.BooleanField(_('公開'), default=True)
    thumbnail = models.ImageField(
        _('サムネイル'), upload_to='notice_thumbnails/', blank=True, null=True,
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('お知らせ')
        verbose_name_plural = _('お知らせ')
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            import uuid as _uuid
            base = slugify(self.title, allow_unicode=True) or 'notice'
            self.slug = f'{base}-{_uuid.uuid4().hex[:8]}'
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('booking:notice_detail', kwargs={'slug': self.slug})

    def excerpt(self, length=100):
        """HTMLタグを除去して抜粋を返す"""
        import re
        text = re.sub(r'<[^>]+>', '', self.content)
        return text[:length] + '...' if len(text) > length else text


class Media(models.Model):
    link = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)
    cached_thumbnail_url = models.URLField(_('サムネイルURL'), blank=True)

    @staticmethod
    def _is_safe_url(url: str) -> bool:
        """内部ネットワークへのアクセスを防ぐURLバリデーション"""
        from urllib.parse import urlparse
        import ipaddress
        import socket
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        # 内部IPアドレスをブロック
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(hostname))
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return False
        except socket.gaierror:
            return False
        except ValueError:
            pass
        return True

    def save(self, *args, **kwargs):
        if self.link and self._is_safe_url(self.link):
            try:
                article = Article(self.link)
                article.download()
                article.parse()
                self.title = article.title[:10] + '...' if len(article.title) > 10 else article.title
                wrapped_text = textwrap.wrap(article.text, width=12)
                self.description = '\n'.join(wrapped_text[:3])
                if article.top_image:
                    self.cached_thumbnail_url = article.top_image
            except Exception:
                pass  # 外部URLの取得失敗時もsave自体は成功させる
        super().save(*args, **kwargs)

    def thumbnail_url(self):
        """キャッシュされたサムネイルURLを返す（毎回ダウンロードしない）"""
        return self.cached_thumbnail_url or ''

    class Meta:
        app_label = 'booking'
        verbose_name = _('メディア掲載情報')
        verbose_name_plural = _('メディア掲載情報')

    def __str__(self):
        return self.title


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
        help_text=_('例: https://twitter.com/youraccount'))
    instagram_url = models.URLField(_('Instagram URL'), blank=True, default='',
        help_text=_('例: https://www.instagram.com/youraccount'))

    # ヒーローバナー
    show_hero_banner = models.BooleanField(_('ヒーローバナー表示'), default=True)

    # 予約ランキング
    show_ranking = models.BooleanField(_('予約ランキング表示'), default=True)
    ranking_limit = models.IntegerField(_('ランキング表示件数'), default=5)

    # 外部リンク
    show_sidebar_external_links = models.BooleanField(_('外部リンク表示'), default=True)

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

    # 法定ページ（HTML編集可能）
    privacy_policy_html = models.TextField(_('プライバシーポリシー'), blank=True, default='',
        help_text=_('HTMLで記述。空の場合はデフォルトテンプレートが表示されます。'))
    tokushoho_html = models.TextField(_('特定商取引法に基づく表記'), blank=True, default='',
        help_text=_('HTMLで記述。空の場合はデフォルトテンプレートが表示されます。'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('メインサイト設定')
        verbose_name_plural = _('メインサイト設定')

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AdminSidebarSettings(SiteSettings):
    """管理画面サイドバー設定 — SiteSettings のプロキシモデル（システム管理用）"""
    class Meta:
        proxy = True
        app_label = 'booking'
        verbose_name = _('管理サイドバー設定')
        verbose_name_plural = _('管理サイドバー設定')


class HomepageCustomBlock(models.Model):
    """WordPress風カスタムHTMLブロック"""
    POSITION_CHOICES = [
        ('above_cards', _('カードの上')),
        ('below_cards', _('カードの下')),
        ('sidebar', _('サイドバー')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    content = models.TextField(_('HTML内容'), help_text=_('HTMLを直接記述できます'))
    position = models.CharField(_('表示位置'), max_length=20, choices=POSITION_CHOICES, default='below_cards')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('カスタムブロック')
        verbose_name_plural = _('カスタムブロック')
        ordering = ['position', 'sort_order']

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class HeroBanner(models.Model):
    """ヒーローバナースライダー"""
    IMAGE_POSITION_CHOICES = [
        ('center', _('中央')),
        ('top', _('上')),
        ('bottom', _('下')),
        ('left', _('左')),
        ('right', _('右')),
        ('top left', _('左上')),
        ('top right', _('右上')),
        ('bottom left', _('左下')),
        ('bottom right', _('右下')),
    ]
    LINK_TYPE_CHOICES = [
        ('none', _('リンクなし')),
        ('store', _('店舗')),
        ('staff', _('占い師')),
        ('url', _('カスタムURL')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    image = models.ImageField(_('バナー画像'), upload_to='hero_banners/')
    image_position = models.CharField(
        _('画像表示位置'), max_length=20,
        choices=IMAGE_POSITION_CHOICES, default='center',
        help_text=_('バナー内で画像のどの部分を表示するかを指定します'),
    )
    link_type = models.CharField(
        _('リンク種別'), max_length=10,
        choices=LINK_TYPE_CHOICES, default='none',
    )
    linked_store = models.ForeignKey(
        'Store', verbose_name=_('リンク先店舗'),
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    linked_staff = models.ForeignKey(
        'Staff', verbose_name=_('リンク先占い師'),
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    link_url = models.URLField(_('リンクURL'), blank=True, default='')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = _('ヒーローバナー')
        verbose_name_plural = _('ヒーローバナー')

    def __str__(self):
        return self.title

    def get_link_url(self):
        """link_type に応じたリンク先URLを返す"""
        from django.urls import reverse
        if self.link_type == 'store' and self.linked_store_id:
            return reverse('booking:staff_list', kwargs={'pk': self.linked_store_id})
        elif self.link_type == 'staff' and self.linked_staff_id:
            return reverse('booking:staff_calendar', kwargs={'pk': self.linked_staff_id})
        elif self.link_type == 'url' and self.link_url:
            return self.link_url
        return ''


class BannerAd(models.Model):
    """バナー広告"""
    POSITION_CHOICES = [
        ('after_hero', _('ヒーローバナーの後')),
        ('after_cards', _('カードの後')),
        ('after_ranking', _('ランキングの後')),
        ('after_campaign', _('キャンペーンの後')),
        ('sidebar', _('サイドバー')),
    ]
    title = models.CharField(_('タイトル'), max_length=200)
    image = models.ImageField(_('バナー画像'), upload_to='banner_ads/')
    link_url = models.URLField(_('リンクURL'), blank=True, default='')
    position = models.CharField(_('表示位置'), max_length=20, choices=POSITION_CHOICES, default='after_hero')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['position', 'sort_order']
        verbose_name = _('バナー広告')
        verbose_name_plural = _('バナー広告')

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class ExternalLink(models.Model):
    """外部リンク"""
    title = models.CharField(_('タイトル'), max_length=200)
    url = models.URLField(_('URL'))
    description = models.TextField(_('説明'), blank=True, default='')
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_active = models.BooleanField(_('公開'), default=True)
    open_in_new_tab = models.BooleanField(_('新しいタブで開く'), default=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = _('外部リンク')
        verbose_name_plural = _('外部リンク')

    def __str__(self):
        return self.title


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


class VisitorCount(models.Model):
    """時間帯別来客集計"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='visitor_counts')
    date = models.DateField(_('日付'), db_index=True)
    hour = models.IntegerField(_('時間帯'))  # 0-23
    pir_count = models.IntegerField(_('PIR検知数'), default=0)
    estimated_visitors = models.IntegerField(_('推定来客数'), default=0)
    order_count = models.IntegerField(_('注文数'), default=0)

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


class StaffRecommendationModel(models.Model):
    """学習済みMLモデル保存"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_models')
    model_file = models.FileField(_('モデルファイル'), upload_to='ml_models/')
    model_type = models.CharField(_('モデル種別'), max_length=50, default='random_forest')
    feature_names = models.JSONField(_('特徴量名'), default=list)
    accuracy_score = models.FloatField(_('精度スコア'), default=0)
    mae_score = models.FloatField(_('MAEスコア'), default=0)
    training_samples = models.IntegerField(_('学習サンプル数'), default=0)
    trained_at = models.DateTimeField(_('学習日時'), auto_now_add=True)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('AI推薦モデル')
        verbose_name_plural = _('AI推薦モデル')
        ordering = ('-trained_at',)

    def __str__(self):
        return f'{self.store.name} {self.model_type} (MAE:{self.mae_score:.2f})'


class StaffRecommendationResult(models.Model):
    """AIスタッフ推薦結果"""
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_results')
    date = models.DateField(_('日付'))
    hour = models.IntegerField(_('時間帯'))  # 0-23
    recommended_staff_count = models.IntegerField(_('推薦スタッフ数'))
    confidence = models.FloatField(_('信頼度'), default=0)
    factors = models.JSONField(_('特徴量重要度'), default=dict)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('AI推薦結果')
        verbose_name_plural = _('AI推薦結果')
        unique_together = ('store', 'date', 'hour')

    def __str__(self):
        return f'{self.store.name} {self.date} {self.hour}時 推薦:{self.recommended_staff_count}人'
