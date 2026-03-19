"""Core models: Store, Staff, Timer, Category, Product, SystemConfig, etc."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import MinValueValidator, MaxValueValidator
from rest_framework import serializers
from django.contrib.auth.models import User

import uuid
from decimal import Decimal
from typing import Optional


# ==============================
# 共通定数
# ==============================
LANG_CHOICES = (
    ('ja', _('日本語')),
    ('en', _('English')),
    ('zh-hant', _('繁體中文')),
    ('zh-hans', _('简体中文')),
    ('ko', _('한국어')),
    ('es', _('Español')),
    ('pt', _('Português')),
)

STAFF_TYPE_CHOICES = [
    ('fortune_teller', _('キャスト')),
    ('store_staff', _('スタッフ')),
]


class Timer(models.Model):
    """LINE タイマー用。views.LINETimerView で end_time を保存しているので、モデルにも持たせる。"""
    user_id = models.CharField(max_length=255, unique=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('タイマー')
        verbose_name_plural = _('タイマー')

    def __str__(self):
        return f"{self.user_id} ({self.start_time} -> {self.end_time})"


class Store(models.Model):
    """店舗一覧"""
    name = models.CharField(_('店名'), max_length=255)
    thumbnail = models.ImageField(_('サムネイル画像'), upload_to='store_thumbnails/', null=True, blank=True)
    address = models.CharField(_('住所'), max_length=255, default='')
    business_hours = models.CharField(_('営業時間'), max_length=255, default='')
    nearest_station = models.CharField(_('最寄り駅'), max_length=255, default='')
    regular_holiday = models.CharField(_('定休日'), max_length=255, default='')
    description = models.TextField(_('店舗情報'), default='', blank=True)
    is_recommended = models.BooleanField(_('おすすめ'), default=False)

    map_url = models.CharField(_('地図URL'), max_length=500, default='', blank=True)
    google_maps_embed = models.TextField(
        _('Google Maps埋め込みコード'),
        default='', blank=True,
        help_text=_('Google Mapsの「共有→地図を埋め込む」からiframeコードを貼り付けてください'),
    )
    access_info = models.TextField(_('アクセス情報'), default='', blank=True)

    # 追加の店舗写真（シンプルに3枚まで）
    photo_2 = models.ImageField(_('店舗写真2'), upload_to='store_photos/', blank=True)
    photo_3 = models.ImageField(_('店舗写真3'), upload_to='store_photos/', blank=True)

    # タイムゾーン
    timezone = models.CharField(
        _('タイムゾーン'), max_length=50, default='Asia/Tokyo',
        help_text=_('店舗のタイムゾーン (例: Asia/Tokyo)'),
    )

    # 追加（多言語）：店舗の既定言語（任意）
    default_language = models.CharField(
        _('既定言語'), max_length=10, default='ja', blank=True, choices=LANG_CHOICES,
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('店舗一覧')
        verbose_name_plural = _('店舗一覧')

    def __str__(self):
        return self.name

    def get_thumbnail_url(self):
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        return settings.STATIC_URL + 'default_thumbnail.jpg'


class Staff(models.Model):
    """在籍占い師スタッフリスト"""
    name = models.CharField(_('表示名'), max_length=50)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_('ログインユーザー'),
        on_delete=models.CASCADE,
        related_name='staff',
    )
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE)
    line_id = models.CharField(_('LINE ID'), max_length=50, null=True, blank=True)

    staff_type = models.CharField(
        _('スタッフ種別'), max_length=20,
        choices=STAFF_TYPE_CHOICES,
        default='fortune_teller',
        db_index=True,
    )

    is_recommended = models.BooleanField(_('おすすめ'), default=False)

    # 追加：仕入れ通知の送信先（店長だけ）
    is_store_manager = models.BooleanField(_('店長'), default=False)
    is_owner = models.BooleanField(_('オーナー'), default=False)
    is_developer = models.BooleanField(_('開発者'), default=False)

    thumbnail = models.ImageField(_('サムネイル画像'), upload_to='thumbnails/', null=True, blank=True)
    introduction = models.TextField(_('自己紹介文'), null=True, blank=True)
    price = models.IntegerField(_('価格'), default=0)

    SLOT_DURATION_CHOICES = [(15, _('15分')), (30, _('30分')), (45, _('45分')), (60, _('60分'))]
    slot_duration = models.IntegerField(
        _('1枠の時間(分)'), choices=SLOT_DURATION_CHOICES,
        null=True, blank=True, default=None,
        help_text=_('未設定の場合は店舗設定を使用'),
    )

    # 通知設定（アカウントごとにON/OFF）
    notify_booking = models.BooleanField(
        _('予約通知'), default=True,
        help_text=_('予約が入った時にLINEで通知を受け取る'),
    )
    notify_shift = models.BooleanField(
        _('シフト通知'), default=True,
        help_text=_('シフト公開・変更時にLINEで通知を受け取る'),
    )
    notify_business = models.BooleanField(
        _('業務連絡通知'), default=True,
        help_text=_('管理者からの業務連絡をLINEで受け取る'),
    )

    # メニュー表示制御（店長が各スタッフに設定）
    can_see_inventory = models.BooleanField(
        _('在庫管理を表示'), default=False,
        help_text=_('ONにすると在庫管理メニューがサイドバーに表示されます'),
    )
    can_see_orders = models.BooleanField(
        _('注文管理を表示'), default=False,
        help_text=_('ONにすると注文管理メニューがサイドバーに表示されます'),
    )

    attendance_pin = models.CharField(
        _('勤怠PIN'), max_length=128, blank=True, default='',
        help_text=_('4桁の打刻用PINコード（ハッシュ化して保存）'),
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('従業員')
        verbose_name_plural = _('従業員一覧')

    def __str__(self):
        return f'{self.store.name} - {self.name}'

    def get_effective_slot_duration(self):
        """個別設定があればそれを、なければ店舗設定にフォールバック"""
        if self.slot_duration is not None:
            return self.slot_duration
        try:
            return self.store.schedule_config.slot_duration
        except Exception:
            return 60

    # --------------------------------------------------
    # 勤怠PIN: ハッシュ化ヘルパー
    # --------------------------------------------------
    def set_attendance_pin(self, raw_pin: str):
        """生の4桁PINをハッシュ化して保存"""
        self.attendance_pin = make_password(raw_pin)

    def check_attendance_pin(self, raw_pin: str) -> bool:
        """入力PINをハッシュと照合。旧データ（平文）との後方互換あり"""
        if not self.attendance_pin:
            return False
        # 旧データ: 平文PINが6文字以下で保存されている場合は直接比較
        if len(self.attendance_pin) <= 6:
            return self.attendance_pin == raw_pin
        return check_password(raw_pin, self.attendance_pin)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class Category(models.Model):
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(_('カテゴリ名'), max_length=100)
    sort_order = models.IntegerField(_('並び順'), default=0)
    is_restaurant_menu = models.BooleanField(_('飲食メニュー表示'), default=True,
        help_text=_('チェックを外すとテーブル注文メニューに表示されません（ECのみ等）'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('商品カテゴリ')
        verbose_name_plural = _('商品カテゴリ')
        unique_together = (('store', 'name'),)
        ordering = ('store', 'sort_order', 'name')

    def __str__(self):
        return f"{self.store.name} / {self.name}"


class Product(models.Model):
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(
        Category,
        verbose_name=_('カテゴリ'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    sku = models.CharField(_('商品コード'), max_length=64, db_index=True)
    name = models.CharField(_('商品名(デフォルト)'), max_length=200)
    description = models.TextField(_('説明(デフォルト)'), blank=True, default='')

    price = models.IntegerField(_('価格'), default=0)

    # 在庫
    stock = models.IntegerField(_('現在庫'), default=0)
    low_stock_threshold = models.IntegerField(_('閾値'), default=0)
    last_low_stock_notified_at = models.DateTimeField(_('閾値通知済み(最後)'), null=True, blank=True)

    is_active = models.BooleanField(_('公開'), default=True)
    is_ec_visible = models.BooleanField(_('EC公開'), default=False, db_index=True,
        help_text=_('チェックするとオンラインショップに表示されます'))
    image = models.ImageField(_('商品画像'), upload_to='product_images/', blank=True, null=True)

    # 代替提案用の簡易スコア（どれを使うかはUI側で選べる）
    popularity = models.IntegerField(_('人気スコア'), default=0)
    margin_rate = models.FloatField(_('利益率(概算)'), default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('商品')
        verbose_name_plural = _('商品')
        unique_together = (('store', 'sku'),)
        indexes = [
            models.Index(fields=['store', 'is_active']),
            models.Index(fields=['store', 'category', 'stock']),
            models.Index(fields=['store', 'sku']),
        ]
        ordering = ('store', 'category', 'name')

    def __str__(self):
        return f"{self.store.name} / {self.sku} / {self.name}"

    @property
    def is_sold_out(self) -> bool:
        return self.stock <= 0

    def should_notify_low_stock(self) -> bool:
        # 閾値割れ検知 + 初回のみ通知
        return self.stock <= self.low_stock_threshold and self.last_low_stock_notified_at is None

    def mark_low_stock_notified(self) -> None:
        self.last_low_stock_notified_at = timezone.now()


class ECCategory(Category):
    """EC商品カテゴリ（プロキシ）"""
    class Meta:
        proxy = True
        app_label = 'booking'
        verbose_name = _('EC商品カテゴリ')
        verbose_name_plural = _('EC商品カテゴリ')


class ECProduct(Product):
    """EC商品（プロキシ）"""
    class Meta:
        proxy = True
        app_label = 'booking'
        verbose_name = _('EC商品')
        verbose_name_plural = _('EC商品')


class ProductTranslation(models.Model):
    """商品データ文言の多言語テーブル"""
    LANG_CHOICES = LANG_CHOICES  # backward compat alias

    product = models.ForeignKey(Product, verbose_name=_('商品'), on_delete=models.CASCADE, related_name='translations')
    lang = models.CharField(_('言語'), max_length=10, choices=LANG_CHOICES, db_index=True)
    name = models.CharField(_('商品名'), max_length=200)
    description = models.TextField(_('説明'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('商品翻訳')
        verbose_name_plural = _('商品翻訳')
        unique_together = (('product', 'lang'),)
        indexes = [
            models.Index(fields=['lang']),
            models.Index(fields=['product', 'lang']),
        ]

    def __str__(self):
        return f"{self.product.sku} ({self.lang})"


class SystemConfig(models.Model):
    """シングルトンパターンのランタイム設定（ログレベル等）"""
    key = models.CharField(_('キー'), max_length=100, unique=True)
    value = models.TextField(_('値'), blank=True, default='')
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('システム設定')
        verbose_name_plural = _('システム設定')

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get(cls, key, default=''):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key, value):
        obj, _ = cls.objects.update_or_create(key=key, defaults={'value': str(value)})
        return obj


class TableSeat(models.Model):
    """店舗テーブル/席"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='table_seats')
    label = models.CharField(_('席名'), max_length=50, help_text=_('例: A1, テーブル1, カウンター3'))
    is_active = models.BooleanField(_('有効'), default=True)
    qr_code = models.ImageField(_('QRコード画像'), upload_to='table_qr/', blank=True, null=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('テーブルQR登録・管理')
        verbose_name_plural = _('テーブルQR登録・管理')
        unique_together = (('store', 'label'),)
        ordering = ('store', 'label')

    def __str__(self):
        return f'{self.store.name} / {self.label}'

    def get_menu_url(self):
        base = getattr(settings, 'SITE_BASE_URL', '')
        return f'{base}/t/{self.id}/'


class TaxServiceCharge(models.Model):
    """税・サービス料設定（消費税、深夜料金等）"""
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='tax_charges')
    name = models.CharField(_('名称'), max_length=100, help_text=_('例: 消費税、深夜料金、サービス料'))
    rate = models.DecimalField(_('税率(%)'), max_digits=5, decimal_places=2, help_text=_('パーセンテージで入力（例: 10.00）'))
    is_active = models.BooleanField(_('有効'), default=True)
    applies_after_hour = models.IntegerField(
        _('適用開始時間'), null=True, blank=True,
        help_text=_('この時間以降に適用（例: 22 = 22時以降）。空欄の場合は常時適用'),
    )
    sort_order = models.IntegerField(_('並び順'), default=0)

    class Meta:
        app_label = 'booking'
        verbose_name = _('税・サービス料')
        verbose_name_plural = _('税・サービス料設定')
        ordering = ('store', 'sort_order')

    def __str__(self):
        hour_info = f' ({self.applies_after_hour}時以降)' if self.applies_after_hour is not None else ''
        return f'{self.store.name} / {self.name} {self.rate}%{hour_info}'


class PaymentMethod(models.Model):
    """店舗別決済方法設定"""
    METHOD_TYPE_CHOICES = [
        ('cash', _('現金')),
        ('coiney', _('Coiney (クレジットカード)')),
        ('paypay', _('PayPay')),
        ('ic', _('IC決済 (交通系/電子マネー)')),
        ('other', _('その他')),
    ]
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='payment_methods')
    method_type = models.CharField(_('決済種別'), max_length=20, choices=METHOD_TYPE_CHOICES)
    display_name = models.CharField(_('表示名'), max_length=100)
    is_enabled = models.BooleanField(_('有効'), default=True)
    api_key = models.CharField(_('APIキー'), max_length=500, blank=True, default='')
    api_secret = models.CharField(_('APIシークレット'), max_length=500, blank=True, default='')
    api_endpoint = models.URLField(_('APIエンドポイント'), blank=True, default='')
    extra_config = models.JSONField(_('追加設定'), default=dict, blank=True)
    sort_order = models.IntegerField(_('並び順'), default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('決済方法')
        verbose_name_plural = _('決済方法')
        unique_together = (('store', 'method_type'),)
        ordering = ('store', 'sort_order')

    def __str__(self):
        return f'{self.store.name} / {self.display_name}'
