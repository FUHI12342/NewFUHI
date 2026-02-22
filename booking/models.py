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
# 共通定数
# ==============================
LANG_CHOICES = (
    ('ja', '日本語'),
    ('en', 'English'),
    ('zh-hant', '繁體中文'),
    ('zh-hans', '简体中文'),
    ('ko', '한국어'),
    ('es', 'Español'),
    ('pt', 'Português'),
)

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
    is_recommended = models.BooleanField('おすすめ', default=False)

    # 追加（多言語）：店舗の既定言語（任意）
    default_language = models.CharField(
        '既定言語', max_length=10, default='ja', blank=True, choices=LANG_CHOICES,
    )

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


STAFF_TYPE_CHOICES = [
    ('fortune_teller', '占い師'),
    ('store_staff', '店舗スタッフ'),
]


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

    staff_type = models.CharField(
        'スタッフ種別', max_length=20,
        choices=STAFF_TYPE_CHOICES,
        default='fortune_teller',
        db_index=True,
    )

    is_recommended = models.BooleanField('おすすめ', default=False)

    # 追加：仕入れ通知の送信先（店長だけ）
    is_store_manager = models.BooleanField('店長', default=False)
    is_owner = models.BooleanField('オーナー', default=False)
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

    # Phase 4b: メール予約対応
    booking_channel = models.CharField(
        '予約経路', max_length=10,
        choices=[('line', 'LINE'), ('email', 'Email')],
        default='line',
    )
    customer_email = models.EmailField('顧客メール', blank=True, null=True)
    email_otp_hash = models.CharField('OTPハッシュ', max_length=64, blank=True, null=True)
    email_otp_expires = models.DateTimeField('OTP有効期限', blank=True, null=True)
    email_verified = models.BooleanField('メール認証済み', default=False)
    payment_url = models.URLField('決済URL', blank=True, null=True)

    # QRチェックイン
    checkin_qr = models.ImageField('チェックインQR', upload_to='checkin_qr/', blank=True, null=True)
    is_checked_in = models.BooleanField('チェックイン済み', default=False)
    checked_in_at = models.DateTimeField('チェックイン日時', blank=True, null=True)

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
    cached_thumbnail_url = models.URLField('サムネイルURL', blank=True)

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
        except (socket.gaierror, ValueError):
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

    external_id = models.CharField('デバイスID（AWS側）', max_length=255, unique=True)
    api_key_hash = models.CharField('APIキーハッシュ', max_length=64, db_index=True, default='',
                                     help_text='SHA-256ハッシュ。認証時の照合用')
    api_key_prefix = models.CharField('APIキープレフィックス', max_length=8, blank=True, default='',
                                       help_text='管理画面表示用（先頭8文字）')

    mq9_threshold = models.FloatField('MQ-9閾値', null=True, blank=True)
    alert_enabled = models.BooleanField('ガス検知アラート有効', default=False)
    alert_email = models.EmailField('アラート送信メール', blank=True)

    wifi_ssid = models.CharField('Wi-Fi SSID', max_length=64, blank=True)
    wifi_password_enc = models.CharField('Wi-Fi パスワード（暗号化）', max_length=512, blank=True)

    @staticmethod
    def _get_iot_fernet():
        """IoT秘密情報用のFernetインスタンスを返す"""
        if Fernet is None:
            raise ImproperlyConfigured("cryptography is required for IoT credential encryption")
        key = getattr(settings, 'IOT_ENCRYPTION_KEY', None)
        if not key:
            raise ImproperlyConfigured("IOT_ENCRYPTION_KEY is not set")
        return Fernet(key.encode('utf-8') if isinstance(key, str) else key)

    def set_wifi_password(self, plain_password: str) -> None:
        """Wi-Fiパスワードを暗号化して保存する"""
        if not plain_password:
            self.wifi_password_enc = ''
            return
        f = self._get_iot_fernet()
        self.wifi_password_enc = f.encrypt(plain_password.encode('utf-8')).decode('utf-8')

    def get_wifi_password(self) -> Optional[str]:
        """暗号化されたWi-Fiパスワードを復号して返す"""
        if not self.wifi_password_enc:
            return None
        try:
            f = self._get_iot_fernet()
            return f.decrypt(self.wifi_password_enc.encode('utf-8')).decode('utf-8')
        except Exception:
            return None

    @staticmethod
    def hash_api_key(raw_key: str) -> str:
        """APIキーのSHA-256ハッシュを返す"""
        return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

    def set_api_key(self, raw_key: str) -> None:
        """APIキーをハッシュ化して保存。生のキーは保存しない。"""
        self.api_key_hash = self.hash_api_key(raw_key)
        self.api_key_prefix = raw_key[:8]

    def verify_api_key(self, raw_key: str) -> bool:
        """APIキーを検証する"""
        return self.api_key_hash == self.hash_api_key(raw_key)

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
    light_value = models.FloatField('照度値', null=True, blank=True, db_index=True)
    sound_value = models.FloatField('音値', null=True, blank=True, db_index=True)
    pir_triggered = models.BooleanField('PIR検知', null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'IoTイベントログ'
        verbose_name_plural = 'IoTイベントログ'
        indexes = [
            models.Index(fields=['device', 'created_at']),
            models.Index(fields=['device', 'mq9_value', 'created_at']),
            models.Index(fields=['device', 'created_at', 'light_value']),
            models.Index(fields=['device', 'created_at', 'sound_value']),
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

    sku = models.CharField('商品コード', max_length=64, db_index=True)
    name = models.CharField('商品名(デフォルト)', max_length=200)
    description = models.TextField('説明(デフォルト)', blank=True, default='')

    price = models.IntegerField('価格', default=0)

    # 在庫
    stock = models.IntegerField('現在庫', default=0)
    low_stock_threshold = models.IntegerField('閾値', default=0)
    last_low_stock_notified_at = models.DateTimeField('閾値通知済み(最後)', null=True, blank=True)

    is_active = models.BooleanField('公開', default=True)
    is_ec_visible = models.BooleanField('EC公開', default=False, db_index=True,
        help_text='チェックするとオンラインショップに表示されます')

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
    LANG_CHOICES = LANG_CHOICES  # backward compat alias

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
    layout_json = models.JSONField('レイアウトJSON', default=list)
    dark_mode = models.BooleanField('ダークモード', default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'ダッシュボードレイアウト'
        verbose_name_plural = 'ダッシュボードレイアウト'

    def __str__(self):
        return f'DashboardLayout({self.user.username})'


# ==============================
# Phase 2: デバッグ / ランタイム設定
# ==============================

class SystemConfig(models.Model):
    """シングルトンパターンのランタイム設定（ログレベル等）"""
    key = models.CharField('キー', max_length=100, unique=True)
    value = models.TextField('値', blank=True, default='')
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'システム設定'
        verbose_name_plural = 'システム設定'

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


# ==============================
# Phase 5: 不動産IoTモニタリング
# ==============================

class Property(models.Model):
    """物件情報"""
    PROPERTY_TYPE_CHOICES = [
        ('apartment', 'アパート/マンション'),
        ('house', '一戸建て'),
        ('office', 'オフィス'),
        ('store', '店舗'),
    ]

    name = models.CharField('物件名', max_length=200)
    address = models.CharField('住所', max_length=300)
    property_type = models.CharField('種別', max_length=20, choices=PROPERTY_TYPE_CHOICES, default='apartment')
    owner_name = models.CharField('オーナー名', max_length=100, blank=True)
    owner_contact = models.CharField('オーナー連絡先', max_length=200, blank=True)
    store = models.ForeignKey(
        Store, verbose_name='関連店舗', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='properties',
    )
    is_active = models.BooleanField('有効', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '物件'
        verbose_name_plural = '物件'

    def __str__(self):
        return self.name


class PropertyDevice(models.Model):
    """物件に設置されたデバイス"""
    property = models.ForeignKey(
        Property, verbose_name='物件', on_delete=models.CASCADE, related_name='property_devices',
    )
    device = models.ForeignKey(
        IoTDevice, verbose_name='デバイス', on_delete=models.CASCADE, related_name='property_placements',
    )
    location_label = models.CharField('設置場所', max_length=100, help_text='例: リビング, 玄関, 寝室')

    class Meta:
        app_label = 'booking'
        verbose_name = '物件デバイス'
        verbose_name_plural = '物件デバイス'
        unique_together = (('property', 'device'),)

    def __str__(self):
        return f"{self.property.name} / {self.location_label} / {self.device.name}"


class PropertyAlert(models.Model):
    """物件アラート"""
    ALERT_TYPE_CHOICES = [
        ('gas_leak', 'ガス漏れ'),
        ('no_motion', '長期不在'),
        ('device_offline', 'デバイスオフライン'),
        ('custom', 'カスタム'),
    ]
    SEVERITY_CHOICES = [
        ('critical', '緊急'),
        ('warning', '警告'),
        ('info', '情報'),
    ]

    property = models.ForeignKey(
        Property, verbose_name='物件', on_delete=models.CASCADE, related_name='alerts',
    )
    device = models.ForeignKey(
        IoTDevice, verbose_name='デバイス', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='property_alerts',
    )
    alert_type = models.CharField('種別', max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField('重要度', max_length=10, choices=SEVERITY_CHOICES, default='info')
    message = models.TextField('メッセージ', blank=True)
    is_resolved = models.BooleanField('解決済み', default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField('解決日時', null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '物件アラート'
        verbose_name_plural = '物件アラート'
        indexes = [
            models.Index(fields=['property', 'is_resolved', 'created_at']),
            models.Index(fields=['alert_type', 'is_resolved']),
        ]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.property.name} - {self.get_alert_type_display()}"


# ==============================
# Phase Round2: シフト管理 + 管理画面
# ==============================

class StoreScheduleConfig(models.Model):
    """店舗営業時間 + 予約コマ設定"""
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='schedule_config')
    open_hour = models.IntegerField('営業開始時間', default=9)      # 0-23
    close_hour = models.IntegerField('営業終了時間', default=21)     # 0-23
    slot_duration = models.IntegerField('予約コマ(分)', default=60,
        help_text='15, 30, 45, 60 のいずれか')

    class Meta:
        app_label = 'booking'
        verbose_name = '店舗スケジュール設定'
        verbose_name_plural = '店舗スケジュール設定'

    def __str__(self):
        return f"{self.store.name} ({self.open_hour}:00-{self.close_hour}:00 / {self.slot_duration}分)"


class ShiftPeriod(models.Model):
    """マネージャーが作成するシフト募集期間（3ヶ月分など）"""
    STATUS_CHOICES = [
        ('open', '募集中'),
        ('closed', '締切'),
        ('scheduled', 'スケジュール済'),
        ('approved', '承認済'),
    ]
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shift_periods')
    year_month = models.DateField('対象年月')  # 月初の日付
    deadline = models.DateTimeField('申請締切')
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'シフト募集期間'
        verbose_name_plural = 'シフト募集期間'

    def __str__(self):
        return f"{self.store.name} {self.year_month.strftime('%Y年%m月')} ({self.get_status_display()})"


class ShiftRequest(models.Model):
    """スタッフのシフト希望"""
    PREF_CHOICES = [
        ('available', '出勤可能'),
        ('preferred', '希望'),
        ('unavailable', '出勤不可'),
    ]
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='requests')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='shift_requests')
    date = models.DateField('日付')
    start_hour = models.IntegerField('開始時間')
    end_hour = models.IntegerField('終了時間')
    preference = models.CharField('希望区分', max_length=20, choices=PREF_CHOICES, default='available')
    note = models.TextField('備考', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'シフト希望'
        verbose_name_plural = 'シフト希望'
        unique_together = ('period', 'staff', 'date', 'start_hour')

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00 ({self.get_preference_display()})"


class ShiftAssignment(models.Model):
    """確定シフト"""
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='assignments')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='shift_assignments')
    date = models.DateField('日付')
    start_hour = models.IntegerField('開始時間')
    end_hour = models.IntegerField('終了時間')
    is_synced = models.BooleanField('Schedule同期済み', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '確定シフト'
        verbose_name_plural = '確定シフト'
        unique_together = ('period', 'staff', 'date', 'start_hour')

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00"


class AdminTheme(models.Model):
    """管理画面UIカスタムテーマ"""
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='admin_theme')
    primary_color = models.CharField('メインカラー', max_length=7, default='#8c876c')
    secondary_color = models.CharField('サブカラー', max_length=7, default='#f1f0ec')
    header_image = models.ImageField('ヘッダー画像', upload_to='admin_themes/', blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '管理画面テーマ'
        verbose_name_plural = '管理画面テーマ'

    def __str__(self):
        return f"{self.store.name} テーマ"


# ==============================
# Round 4: ホームページCMS
# ==============================

class SiteSettings(models.Model):
    """サイト全体の設定 (シングルトン)"""
    site_name = models.CharField('サイト名', max_length=200, default='占いサロンチャンス')

    # ホームページカードON/OFF
    show_card_store = models.BooleanField('店舗カード表示', default=True)
    show_card_fortune_teller = models.BooleanField('占い師カード表示', default=True)
    show_card_calendar = models.BooleanField('カレンダーカード表示', default=True)
    show_card_shop = models.BooleanField('ショップカード表示', default=True)

    # サイドバーON/OFF
    show_sidebar_notice = models.BooleanField('お知らせ表示', default=True)
    show_sidebar_company = models.BooleanField('運営会社表示', default=True)
    show_sidebar_media = models.BooleanField('メディア掲載表示', default=True)
    show_sidebar_social = models.BooleanField('SNSフィード表示', default=False)

    # SNS連携URL
    twitter_url = models.URLField('X(Twitter) URL', blank=True, default='',
        help_text='例: https://twitter.com/youraccount')
    instagram_url = models.URLField('Instagram URL', blank=True, default='',
        help_text='例: https://www.instagram.com/youraccount')

    # ヒーローバナー
    show_hero_banner = models.BooleanField('ヒーローバナー表示', default=True)

    # 予約ランキング
    show_ranking = models.BooleanField('予約ランキング表示', default=True)
    ranking_limit = models.IntegerField('ランキング表示件数', default=5)

    # 外部リンク
    show_sidebar_external_links = models.BooleanField('外部リンク表示', default=True)

    # Instagram埋め込みHTML
    instagram_embed_html = models.TextField('Instagram埋め込みHTML', blank=True, default='',
        help_text='Instagramの投稿埋め込みHTMLを貼り付けてください')

    class Meta:
        app_label = 'booking'
        verbose_name = 'サイト設定'
        verbose_name_plural = 'サイト設定'

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class HomepageCustomBlock(models.Model):
    """WordPress風カスタムHTMLブロック"""
    POSITION_CHOICES = [
        ('above_cards', 'カードの上'),
        ('below_cards', 'カードの下'),
        ('sidebar', 'サイドバー'),
    ]
    title = models.CharField('タイトル', max_length=200)
    content = models.TextField('HTML内容', help_text='HTMLを直接記述できます')
    position = models.CharField('表示位置', max_length=20, choices=POSITION_CHOICES, default='below_cards')
    sort_order = models.IntegerField('並び順', default=0)
    is_active = models.BooleanField('公開', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'カスタムブロック'
        verbose_name_plural = 'カスタムブロック'
        ordering = ['position', 'sort_order']

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class HeroBanner(models.Model):
    """ヒーローバナースライダー"""
    IMAGE_POSITION_CHOICES = [
        ('center', '中央'),
        ('top', '上'),
        ('bottom', '下'),
        ('left', '左'),
        ('right', '右'),
        ('top left', '左上'),
        ('top right', '右上'),
        ('bottom left', '左下'),
        ('bottom right', '右下'),
    ]
    LINK_TYPE_CHOICES = [
        ('none', 'リンクなし'),
        ('store', '店舗'),
        ('staff', '占い師'),
        ('url', 'カスタムURL'),
    ]
    title = models.CharField('タイトル', max_length=200)
    image = models.ImageField('バナー画像', upload_to='hero_banners/')
    image_position = models.CharField(
        '画像表示位置', max_length=20,
        choices=IMAGE_POSITION_CHOICES, default='center',
        help_text='バナー内で画像のどの部分を表示するかを指定します',
    )
    link_type = models.CharField(
        'リンク種別', max_length=10,
        choices=LINK_TYPE_CHOICES, default='none',
    )
    linked_store = models.ForeignKey(
        'Store', verbose_name='リンク先店舗',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    linked_staff = models.ForeignKey(
        'Staff', verbose_name='リンク先占い師',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    link_url = models.URLField('リンクURL', blank=True, default='')
    sort_order = models.IntegerField('並び順', default=0)
    is_active = models.BooleanField('公開', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = 'ヒーローバナー'
        verbose_name_plural = 'ヒーローバナー'

    def __str__(self):
        return self.title

    def get_link_url(self):
        """link_type に応じたリンク先URLを返す"""
        if self.link_type == 'store' and self.linked_store_id:
            return f'/booking/store/{self.linked_store_id}/staffs/'
        elif self.link_type == 'staff' and self.linked_staff_id:
            return f'/booking/staff/{self.linked_staff_id}/calendar/'
        elif self.link_type == 'url' and self.link_url:
            return self.link_url
        return ''


class BannerAd(models.Model):
    """バナー広告"""
    POSITION_CHOICES = [
        ('after_hero', 'ヒーローバナーの後'),
        ('after_cards', 'カードの後'),
        ('after_ranking', 'ランキングの後'),
        ('after_campaign', 'キャンペーンの後'),
        ('sidebar', 'サイドバー'),
    ]
    title = models.CharField('タイトル', max_length=200)
    image = models.ImageField('バナー画像', upload_to='banner_ads/')
    link_url = models.URLField('リンクURL', blank=True, default='')
    position = models.CharField('表示位置', max_length=20, choices=POSITION_CHOICES, default='after_hero')
    sort_order = models.IntegerField('並び順', default=0)
    is_active = models.BooleanField('公開', default=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        ordering = ['position', 'sort_order']
        verbose_name = 'バナー広告'
        verbose_name_plural = 'バナー広告'

    def __str__(self):
        return f'{self.title} ({self.get_position_display()})'


class ExternalLink(models.Model):
    """外部リンク"""
    title = models.CharField('タイトル', max_length=200)
    url = models.URLField('URL')
    description = models.TextField('説明', blank=True, default='')
    sort_order = models.IntegerField('並び順', default=0)
    is_active = models.BooleanField('公開', default=True)
    open_in_new_tab = models.BooleanField('新しいタブで開く', default=True)

    class Meta:
        app_label = 'booking'
        ordering = ['sort_order']
        verbose_name = '外部リンク'
        verbose_name_plural = '外部リンク'

    def __str__(self):
        return self.title


# ==============================
# 管理画面メニュー権限設定
# ==============================

# ==============================
# 給与管理・勤怠管理
# ==============================

class EmploymentContract(models.Model):
    """雇用契約（Staff 1:1）"""
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', '正社員'),
        ('part_time', 'パート・アルバイト'),
        ('contract', '契約社員'),
    ]
    PAY_TYPE_CHOICES = [
        ('hourly', '時給'),
        ('monthly', '月給'),
    ]

    staff = models.OneToOneField(
        Staff, verbose_name='スタッフ', on_delete=models.CASCADE, related_name='employment_contract',
    )
    employment_type = models.CharField('雇用形態', max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='part_time')
    pay_type = models.CharField('給与形態', max_length=10, choices=PAY_TYPE_CHOICES, default='hourly')
    hourly_rate = models.IntegerField('時給（円）', default=0, help_text='時給制の場合に設定')
    monthly_salary = models.IntegerField('月給（円）', default=0, help_text='月給制の場合に設定')

    commute_allowance = models.IntegerField('通勤手当（円/月）', default=0)
    housing_allowance = models.IntegerField('住宅手当（円/月）', default=0)
    family_allowance = models.IntegerField('家族手当（円/月）', default=0)

    standard_monthly_remuneration = models.IntegerField(
        '標準報酬月額（円）', default=0,
        help_text='社会保険料計算の基準額。4〜6月の平均報酬から算定。',
    )
    resident_tax_monthly = models.IntegerField('住民税月額（円）', default=0, help_text='特別徴収の月額')

    birth_date = models.DateField('生年月日', null=True, blank=True, help_text='介護保険適用判定に使用（40歳以上）')
    contract_start = models.DateField('契約開始日', null=True, blank=True)
    contract_end = models.DateField('契約終了日', null=True, blank=True)
    is_active = models.BooleanField('有効', default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '雇用契約'
        verbose_name_plural = '雇用契約'

    def __str__(self):
        return f'{self.staff.name} ({self.get_employment_type_display()} / {self.get_pay_type_display()})'


class WorkAttendance(models.Model):
    """勤怠記録"""
    SOURCE_CHOICES = [
        ('shift', 'シフトから自動生成'),
        ('manual', '手動入力'),
        ('corrected', '修正済み'),
    ]

    staff = models.ForeignKey(Staff, verbose_name='スタッフ', on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField('日付', db_index=True)
    clock_in = models.TimeField('出勤時刻', null=True, blank=True)
    clock_out = models.TimeField('退勤時刻', null=True, blank=True)

    regular_minutes = models.IntegerField('通常勤務（分）', default=0)
    overtime_minutes = models.IntegerField('残業（分）', default=0)
    late_night_minutes = models.IntegerField('深夜勤務（分）', default=0)
    holiday_minutes = models.IntegerField('休日勤務（分）', default=0)
    break_minutes = models.IntegerField('休憩（分）', default=0)

    source = models.CharField('データソース', max_length=20, choices=SOURCE_CHOICES, default='shift')
    source_assignment = models.ForeignKey(
        ShiftAssignment, verbose_name='元シフト', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='derived_attendances',
    )

    class Meta:
        app_label = 'booking'
        verbose_name = '勤怠記録'
        verbose_name_plural = '勤怠記録'
        unique_together = ('staff', 'date')
        indexes = [
            models.Index(fields=['staff', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f'{self.staff.name} {self.date} ({self.get_source_display()})'

    @property
    def total_work_minutes(self):
        return self.regular_minutes + self.overtime_minutes + self.late_night_minutes + self.holiday_minutes


class PayrollPeriod(models.Model):
    """給与計算期間"""
    STATUS_CHOICES = [
        ('draft', '下書き'),
        ('calculating', '計算中'),
        ('confirmed', '確定'),
        ('paid', '支払済'),
    ]

    store = models.ForeignKey(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='payroll_periods')
    year_month = models.CharField('対象年月', max_length=7, help_text='YYYY-MM形式')
    period_start = models.DateField('計算期間開始')
    period_end = models.DateField('計算期間終了')
    status = models.CharField('状態', max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_date = models.DateField('支給日', null=True, blank=True)
    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '給与計算期間'
        verbose_name_plural = '給与計算期間'
        unique_together = ('store', 'year_month')

    def __str__(self):
        return f'{self.store.name} {self.year_month} ({self.get_status_display()})'


class PayrollEntry(models.Model):
    """個人別給与明細"""
    period = models.ForeignKey(PayrollPeriod, verbose_name='給与期間', on_delete=models.CASCADE, related_name='entries')
    staff = models.ForeignKey(Staff, verbose_name='スタッフ', on_delete=models.CASCADE, related_name='payroll_entries')
    contract = models.ForeignKey(
        EmploymentContract, verbose_name='雇用契約', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payroll_entries',
    )

    total_work_days = models.IntegerField('出勤日数', default=0)
    total_regular_hours = models.DecimalField('通常勤務時間', max_digits=6, decimal_places=2, default=0)
    total_overtime_hours = models.DecimalField('残業時間', max_digits=6, decimal_places=2, default=0)
    total_late_night_hours = models.DecimalField('深夜勤務時間', max_digits=6, decimal_places=2, default=0)
    total_holiday_hours = models.DecimalField('休日勤務時間', max_digits=6, decimal_places=2, default=0)

    base_pay = models.IntegerField('基本給', default=0)
    overtime_pay = models.IntegerField('残業手当', default=0)
    late_night_pay = models.IntegerField('深夜手当', default=0)
    holiday_pay = models.IntegerField('休日手当', default=0)
    allowances = models.IntegerField('各種手当合計', default=0, help_text='通勤+住宅+家族手当')

    gross_pay = models.IntegerField('総支給額', default=0)
    total_deductions = models.IntegerField('控除合計', default=0)
    net_pay = models.IntegerField('差引支給額', default=0)

    created_at = models.DateTimeField('作成日時', auto_now_add=True)
    updated_at = models.DateTimeField('更新日時', auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = '給与明細'
        verbose_name_plural = '給与明細'
        unique_together = ('period', 'staff')

    def __str__(self):
        return f'{self.staff.name} {self.period.year_month} 総支給:{self.gross_pay:,}円'


class PayrollDeduction(models.Model):
    """控除明細行"""
    DEDUCTION_TYPE_CHOICES = [
        ('income_tax', '所得税（源泉徴収）'),
        ('resident_tax', '住民税'),
        ('pension', '厚生年金'),
        ('health_insurance', '健康保険'),
        ('employment_insurance', '雇用保険'),
        ('long_term_care', '介護保険'),
        ('workers_comp', '労災保険'),
        ('other', 'その他'),
    ]

    entry = models.ForeignKey(PayrollEntry, verbose_name='給与明細', on_delete=models.CASCADE, related_name='deductions')
    deduction_type = models.CharField('控除種別', max_length=30, choices=DEDUCTION_TYPE_CHOICES)
    amount = models.IntegerField('金額', default=0)
    is_employer_only = models.BooleanField('事業主負担のみ', default=False, help_text='労災保険等、従業員控除なし')

    class Meta:
        app_label = 'booking'
        verbose_name = '控除明細'
        verbose_name_plural = '控除明細'

    def __str__(self):
        label = self.get_deduction_type_display()
        return f'{label}: {self.amount:,}円'


class SalaryStructure(models.Model):
    """給与体系（Store 1:1）— 社会保険料率・割増率"""
    store = models.OneToOneField(Store, verbose_name='店舗', on_delete=models.CASCADE, related_name='salary_structure')

    # 社会保険料率（従業員負担分、%表記→小数で格納）
    pension_rate = models.DecimalField('厚生年金料率(%)', max_digits=5, decimal_places=3, default=9.150,
        help_text='従業員負担分 例: 9.150')
    health_insurance_rate = models.DecimalField('健康保険料率(%)', max_digits=5, decimal_places=3, default=5.000,
        help_text='従業員負担分 例: 5.000（協会けんぽ東京支部）')
    employment_insurance_rate = models.DecimalField('雇用保険料率(%)', max_digits=5, decimal_places=3, default=0.600,
        help_text='従業員負担分 例: 0.600')
    long_term_care_rate = models.DecimalField('介護保険料率(%)', max_digits=5, decimal_places=3, default=0.820,
        help_text='40歳以上のみ適用 例: 0.820')
    workers_comp_rate = models.DecimalField('労災保険料率(%)', max_digits=5, decimal_places=3, default=0.300,
        help_text='事業主全額負担（記録用） 例: 0.300')

    # 割増率
    overtime_multiplier = models.DecimalField('残業割増率', max_digits=4, decimal_places=2, default=1.25)
    late_night_multiplier = models.DecimalField('深夜割増率', max_digits=4, decimal_places=2, default=1.35)
    holiday_multiplier = models.DecimalField('休日割増率', max_digits=4, decimal_places=2, default=1.50)

    class Meta:
        app_label = 'booking'
        verbose_name = '給与体系'
        verbose_name_plural = '給与体系'

    def __str__(self):
        return f'{self.store.name} 給与体系'


class AdminMenuConfig(models.Model):
    """ロールごとの管理画面サイドバー表示メニュー設定"""
    ROLE_CHOICES = [
        ('developer', '開発者'),
        ('owner', 'オーナー'),
        ('manager', '店長'),
        ('staff', 'スタッフ'),
    ]
    role = models.CharField('ロール', max_length=20, choices=ROLE_CHOICES, unique=True,
        help_text='superuserは常に全モデルを表示するため設定不要')
    allowed_models = models.JSONField('表示許可モデル', default=list)
    updated_at = models.DateTimeField('更新日時', auto_now=True)
    updated_by = models.ForeignKey('auth.User', verbose_name='更新者',
        on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = 'メニュー権限設定'
        verbose_name_plural = 'メニュー権限設定'

    def __str__(self):
        return f'{self.get_role_display()} メニュー設定'