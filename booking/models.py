from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured

from rest_framework import serializers
from django.contrib.auth.models import User

import uuid
from newspaper import Article
import textwrap
import hashlib
from typing import Optional
from django.db import transaction

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


# ==============================
# 既存（あなたの貼ってくれたコード）ここから
# ==============================

class Timer(models.Model):
    """LINE タイマー用。views.LINETimerView で end_time を保存しているので、モデルにも持たせる。"""
    user_id = models.CharField(max_length=255, unique=True)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'タイマー'
        verbose_name_plural = 'タイマー'

    def __str__(self):
        return f"{self.user_id} ({self.start_time} -> {self.end_time})"


class Store(models.Model):
    """店舗一覧"""
    name = models.CharField('店名', max_length=255)
    thumbnail = models.ImageField('サムネイル画像', upload_to='store_thumbnails/', null=True, blank=True)
    address = models.CharField('住所', max_length=255, default='')
    business_hours = models.CharField('営業時間', max_length=255, default='')
    nearest_station = models.CharField('最寄り駅', max_length=255, default='')
    regular_holiday = models.CharField('定休日', max_length=255, default='')
    description = models.TextField('店舗情報', default='', blank=True)

    # 追加（多言語）：店舗の既定言語（任意）
    default_language = models.CharField('既定言語', max_length=10, default='ja', blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '店舗一覧'
        verbose_name_plural = '店舗一覧'

    def __str__(self):
        return self.name

    def get_thumbnail_url(self):
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        return settings.STATIC_URL + 'default_thumbnail.jpg'


class Staff(models.Model):
    """在籍占い師スタッフリスト"""
    name = models.CharField('表示名', max_length=50)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name='ログインユーザー',
        on_delete=models.CASCADE,
        related_name='staff',
    )
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE)
    line_id = models.CharField('LINE ID', max_length=50, null=True, blank=True)

    # 追加：仕入れ通知の送信先（店長だけ）
    is_store_manager = models.BooleanField('店長', default=False)
    is_developer = models.BooleanField('開発者', default=False)

    thumbnail = models.ImageField('サムネイル画像', upload_to='thumbnails/', null=True, blank=True)
    introduction = models.TextField('自己紹介文', null=True, blank=True)
    price = models.IntegerField('価格', default=0)

    class Meta:
        app_label = 'booking'
        verbose_name = '在籍占い師スタッフリスト'
        verbose_name_plural = '在籍占い師スタッフリスト'

    def __str__(self):
        return f'{self.store.name} - {self.name}'


class Schedule(models.Model):
    """予約スケジュール."""
    reservation_number = models.CharField(
        '予約番号',
        max_length=255,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    start = models.DateTimeField('開始時間', db_index=True)
    end = models.DateTimeField('終了時間')
    staff = models.ForeignKey('Staff', verbose_name='占いスタッフ', on_delete=models.CASCADE, db_index=True)

    customer_name = models.CharField(max_length=255, null=True, blank=True)
    hashed_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # ▼追加：生のLINE user_idは保存しない（検索用ハッシュ + 復号用暗号文のみ保存）
    line_user_hash = models.CharField('LINEユーザーIDハッシュ', max_length=64, null=True, blank=True, db_index=True)
    line_user_enc = models.TextField('LINEユーザーID(暗号化)', null=True, blank=True)

    is_temporary = models.BooleanField('仮予約フラグ', default=True, db_index=True)
    is_cancelled = models.BooleanField('キャンセルフラグ', default=False, db_index=True)

    price = models.IntegerField('価格', default=0)
    memo = models.TextField('備考', blank=True, null=True, default='ここに備考を記入してください。')
    temporary_booked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '予約確定済みのスケジュール'
        verbose_name_plural = '予約確定済みのスケジュール'
        indexes = [
            models.Index(fields=['staff', 'start']),
            models.Index(fields=['staff', 'is_temporary', 'start']),
            models.Index(fields=['staff', 'is_cancelled', 'start']),
            models.Index(fields=['line_user_hash']),
        ]

    def __str__(self):
        start = timezone.localtime(self.start).strftime('%Y/%m/%d %H:%M:%S')
        end = timezone.localtime(self.end).strftime('%Y/%m/%d %H:%M:%S')
        customer_name = self.customer_name if self.customer_name else "No customer"
        return f'{self.reservation_number} {start} ~ {end} {self.staff} Customer: {customer_name}'

    # ===== LINE user_id 保管（暗号化 + ハッシュ） =====
    @staticmethod
    def _get_line_id_fernet():
        """Fernet を返す。settings.LINE_USER_ID_ENCRYPTION_KEY が必須。"""
        if Fernet is None:
            raise ImproperlyConfigured("cryptography is required for LINE user id encryption")

        key = getattr(settings, 'LINE_USER_ID_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured("LINE_USER_ID_ENCRYPTION_KEY is not set")

        if isinstance(key, str):
            key_bytes = key.encode('utf-8')
        else:
            key_bytes = key

        return Fernet(key_bytes)

    @staticmethod
    def make_line_user_hash(line_user_id: str) -> str:
        """DB検索用の不可逆ハッシュ（pepper + SHA-256）。"""
        pepper = getattr(settings, 'LINE_USER_ID_HASH_PEPPER', '')
        base = f"{pepper}{line_user_id}".encode('utf-8')
        return hashlib.sha256(base).hexdigest()

    def set_line_user_id(self, line_user_id: str) -> None:
        """生の LINE user_id を受け取り、ハッシュ + 暗号文を保存する（生値は保存しない）。"""
        if not line_user_id:
            self.line_user_hash = None
            self.line_user_enc = None
            return

        f = self._get_line_id_fernet()
        token = f.encrypt(line_user_id.encode('utf-8'))
        self.line_user_enc = token.decode('utf-8')
        self.line_user_hash = self.make_line_user_hash(line_user_id)

    def get_line_user_id(self) -> Optional[str]:
        """暗号文から復号して生の LINE user_id を返す。"""
        if not self.line_user_enc:
            return None
        f = self._get_line_id_fernet()
        try:
            raw = f.decrypt(self.line_user_enc.encode('utf-8'))
            return raw.decode('utf-8')
        except Exception:
            return None

    @property
    def has_line_user(self) -> bool:
        return bool(self.line_user_enc)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']


class Company(models.Model):
    name = models.CharField('会社名', max_length=255)
    address = models.CharField('住所', max_length=255)
    tel = models.CharField('電話番号', max_length=20, default='000-0000-0000')

    class Meta:
        app_label = 'booking'
        verbose_name = '運営会社情報'
        verbose_name_plural = '運営会社情報'

    def __str__(self):
        return self.name


class Notice(models.Model):
    updated_at = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=200)
    link = models.URLField()
    content = models.TextField(default='')

    class Meta:
        app_label = 'booking'
        verbose_name = 'お知らせ'
        verbose_name_plural = 'お知らせ'

    def __str__(self):
        return self.title


class Media(models.Model):
    link = models.URLField()
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        article = Article(self.link)
        article.download()
        article.parse()
        self.title = article.title[:10] + '...' if len(article.title) > 10 else article.title
        wrapped_text = textwrap.wrap(article.text, width=12)
        self.description = '\n'.join(wrapped_text[:3])
        super().save(*args, **kwargs)

    def thumbnail_url(self):
        article = Article(self.link)
        article.download()
        article.parse()
        return article.top_image

    class Meta:
        app_label = 'booking'
        verbose_name = 'メディア掲載情報'
        verbose_name_plural = 'メディア掲載情報'

    def __str__(self):
        return self.title


class IoTDevice(models.Model):
    """Pico + センサーを含む IoT デバイス情報"""
    DEVICE_TYPE_CHOICES = [
        ('multi', 'マルチセンサーノード'),
        ('door', 'スマートロック'),
        ('other', 'その他'),
    ]

    name = models.CharField('デバイス名', max_length=100)
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='iot_devices')
    device_type = models.CharField('種別', choices=DEVICE_TYPE_CHOICES, max_length=20, default='multi')

    external_id = models.CharField('デバイスID（AWS側）', max_length=255, unique=True, db_index=True)
    api_key = models.CharField('APIキー', max_length=255, db_index=True)

    mq9_threshold = models.FloatField('MQ-9閾値', null=True, blank=True)
    alert_enabled = models.BooleanField('ガス検知アラート有効', default=False)
    alert_email = models.EmailField('アラート送信メール', blank=True)

    wifi_ssid = models.CharField('Wi-Fi SSID', max_length=64, blank=True)
    wifi_password = models.CharField('Wi-Fi パスワード', max_length=128, blank=True)

    is_active = models.BooleanField('有効', default=True)
    last_seen_at = models.DateTimeField('最終通信日時', null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'IoTデバイス'
        verbose_name_plural = 'IoTデバイス'

    def __str__(self):
        return f'{self.store.name} / {self.name}'


class IoTEvent(models.Model):
    """IoT デバイスから送信されたセンサーログ"""
    device = models.ForeignKey(IoTDevice, verbose_name='デバイス', on_delete=models.CASCADE, related_name='events')
    created_at = models.DateTimeField('受信日時', auto_now_add=True, db_index=True)
    event_type = models.CharField('イベント種別', max_length=50, blank=True)
    payload = models.TextField('ペイロード(JSON)', blank=True)
    mq9_value = models.FloatField('MQ-9値', null=True, blank=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'IoTイベントログ'
        verbose_name_plural = 'IoTイベントログ'
        indexes = [
            models.Index(fields=['device', 'created_at']),
            models.Index(fields=['device', 'mq9_value', 'created_at']),
        ]

    def __str__(self):
        return f'{self.device} @ {self.created_at}'


# ==============================
# 追加: 在庫 / 注文 / 入庫QR / 翻訳
# ==============================

class Category(models.Model):
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField('カテゴリ名', max_length=100)
    sort_order = models.IntegerField('並び順', default=0)

    class Meta:
        app_label = 'booking'
        verbose_name = '商品カテゴリ'
        verbose_name_plural = '商品カテゴリ'
        unique_together = (('store', 'name'),)
        ordering = ('store', 'sort_order', 'name')

    def __str__(self):
        return f"{self.store.name} / {self.name}"


class Product(models.Model):
    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(
        Category,
        verbose_name='カテゴリ',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products'
    )

    sku = models.CharField('SKU', max_length=64, db_index=True)
    name = models.CharField('商品名(デフォルト)', max_length=200)
    description = models.TextField('説明(デフォルト)', blank=True, default='')

    price = models.IntegerField('価格', default=0)

    # 在庫
    stock = models.IntegerField('現在庫', default=0)
    low_stock_threshold = models.IntegerField('閾値', default=0)
    last_low_stock_notified_at = models.DateTimeField('閾値通知済み(最後)', null=True, blank=True)

    is_active = models.BooleanField('公開', default=True)

    # 代替提案用の簡易スコア（どれを使うかはUI側で選べる）
    popularity = models.IntegerField('人気スコア', default=0)
    margin_rate = models.FloatField('利益率(概算)', default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '商品'
        verbose_name_plural = '商品'
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


class ProductTranslation(models.Model):
    """商品データ文言の多言語テーブル"""
    LANG_CHOICES = (
        ('ja', '日本語'),
        ('en', 'English'),
        ('zh-hant', '繁體中文'),
        ('zh-hans', '简体中文'),
        ('ko', '한국어'),
        ('es', 'Español'),
        ('pt', 'Português'),
    )

    product = models.ForeignKey(Product, verbose_name='商品', on_delete=models.CASCADE, related_name='translations')
    lang = models.CharField('言語', max_length=10, choices=LANG_CHOICES, db_index=True)
    name = models.CharField('商品名', max_length=200)
    description = models.TextField('説明', blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = '商品翻訳'
        verbose_name_plural = '商品翻訳'
        unique_together = (('product', 'lang'),)
        indexes = [
            models.Index(fields=['lang']),
            models.Index(fields=['product', 'lang']),
        ]

    def __str__(self):
        return f"{self.product.sku} ({self.lang})"


class Order(models.Model):
    """注文（セッション/会計単位のかたまり）"""

    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
    )

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='orders')
    schedule = models.ForeignKey(
        Schedule,
        verbose_name='予約',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    customer_line_user_hash = models.CharField('顧客LINEハッシュ', max_length=64, null=True, blank=True, db_index=True)
    table_label = models.CharField('席/テーブル', max_length=50, blank=True, default='')

    status = models.CharField('状態', max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '注文'
        verbose_name_plural = '注文'
        indexes = [
            models.Index(fields=['store', 'status', 'created_at']),
            models.Index(fields=['customer_line_user_hash', 'created_at']),
        ]

    def __str__(self):
        return f"Order#{self.id} {self.store.name} ({self.status})"


class OrderItem(models.Model):
    """注文明細"""

    STATUS_ORDERED = 'ORDERED'
    STATUS_PREPARING = 'PREPARING'
    STATUS_SERVED = 'SERVED'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_ORDERED, 'Ordered'),
        (STATUS_PREPARING, 'Preparing'),
        (STATUS_SERVED, 'Served'),
        (STATUS_CLOSED, 'Closed'),
    )

    order = models.ForeignKey(Order, verbose_name='注文', on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, verbose_name='商品', on_delete=models.PROTECT, related_name='order_items')

    qty = models.IntegerField('数量', default=1)
    unit_price = models.IntegerField('単価', default=0)

    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default=STATUS_ORDERED, db_index=True)
    note = models.CharField('備考', max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '注文明細'
        verbose_name_plural = '注文明細'
        indexes = [
            models.Index(fields=['order', 'status', 'created_at']),
            models.Index(fields=['product', 'created_at']),
        ]

    def __str__(self):
        return f"OrderItem#{self.id} {self.product.sku} x{self.qty} ({self.status})"


class StockMovement(models.Model):
    """入出庫履歴（棚卸/入庫QR/注文引当のベース）"""

    TYPE_IN = 'IN'
    TYPE_OUT = 'OUT'
    TYPE_ADJUST = 'ADJUST'
    TYPE_CHOICES = (
        (TYPE_IN, '入庫'),
        (TYPE_OUT, '出庫'),
        (TYPE_ADJUST, '棚卸調整'),
    )

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, verbose_name='商品', on_delete=models.PROTECT, related_name='stock_movements')

    movement_type = models.CharField('種別', max_length=10, choices=TYPE_CHOICES, db_index=True)
    qty = models.IntegerField('数量')

    by_staff = models.ForeignKey(Staff, verbose_name='実施スタッフ', on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField('メモ', max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '入出庫履歴'
        verbose_name_plural = '入出庫履歴'
        indexes = [
            models.Index(fields=['store', 'created_at']),
            models.Index(fields=['product', 'created_at']),
            models.Index(fields=['movement_type', 'created_at']),
        ]

    def __str__(self):
        return f"{self.store.name} {self.product.sku} {self.movement_type} {self.qty}"


def apply_stock_movement(
    product: "Product",
    movement_type: str,
    qty: int,
    *,
    allow_negative: bool = False,
) -> None:
    """在庫数を更新するユーティリティ（同時更新に強い版）。

    - Product行を select_for_update() でロックしてから更新
    - IN: +abs(qty)
    - OUT: -abs(qty)
    - ADJUST: qty(差分)
    """
    q = int(qty)

    if movement_type == StockMovement.TYPE_IN:
        delta = abs(q)
    elif movement_type == StockMovement.TYPE_OUT:
        delta = -abs(q)
    elif movement_type == StockMovement.TYPE_ADJUST:
        delta = q
    else:
        raise ValueError("invalid movement_type")

    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product.pk)

        new_stock = int(locked.stock) + int(delta)
        if (not allow_negative) and new_stock < 0:
            raise ValueError("stock would become negative")

        # 在庫更新（競合に強い）
        Product.objects.filter(pk=locked.pk).update(stock=F("stock") + delta)

        # 更新後の状態で閾値判定
        locked.refresh_from_db(fields=["stock", "low_stock_threshold", "last_low_stock_notified_at", "updated_at"])

        # 在庫が閾値より上に戻ったら通知フラグ解除
        if int(locked.stock) > int(locked.low_stock_threshold):
            if locked.last_low_stock_notified_at is not None:
                Product.objects.filter(pk=locked.pk).update(last_low_stock_notified_at=None)
                locked.last_low_stock_notified_at = None

        # 呼び出し元インスタンスにも反映
        product.stock = locked.stock
        product.last_low_stock_notified_at = locked.last_low_stock_notified_at
        product.updated_at = locked.updated_at