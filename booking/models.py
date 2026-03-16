from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.hashers import make_password, check_password
from django.core.validators import RegexValidator

from rest_framework import serializers
from django.contrib.auth.models import User

import uuid
from decimal import Decimal
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
    access_info = models.TextField(_('アクセス情報'), default='', blank=True)

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


STAFF_TYPE_CHOICES = [
    ('fortune_teller', '占い師'),
    ('store_staff', '店舗スタッフ'),
]


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

    attendance_pin = models.CharField(
        _('勤怠PIN'), max_length=128, blank=True, default='',
        help_text=_('4桁の打刻用PINコード（ハッシュ化して保存）'),
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('キャスト')
        verbose_name_plural = _('キャスト一覧')

    def __str__(self):
        return f'{self.store.name} - {self.name}'

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


class Schedule(models.Model):
    """予約スケジュール."""
    # TODO: max_length=255 is excessive for UUID (36 chars).
    # Consider changing to max_length=36 with a migration once confirmed
    # no non-UUID values exist in production data.
    reservation_number = models.CharField(
        _('予約番号'),
        max_length=255,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    start = models.DateTimeField(_('開始時間'), db_index=True)
    end = models.DateTimeField(_('終了時間'))
    staff = models.ForeignKey('Staff', verbose_name=_('占いスタッフ'), on_delete=models.CASCADE, db_index=True)

    customer_name = models.CharField(max_length=255, null=True, blank=True)
    hashed_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)

    # ▼追加：生のLINE user_idは保存しない（検索用ハッシュ + 復号用暗号文のみ保存）
    line_user_hash = models.CharField(_('LINEユーザーIDハッシュ'), max_length=64, null=True, blank=True, db_index=True)
    line_user_enc = models.TextField(_('LINEユーザーID(暗号化)'), null=True, blank=True)

    is_temporary = models.BooleanField(_('仮予約フラグ'), default=True, db_index=True)
    is_cancelled = models.BooleanField(_('キャンセルフラグ'), default=False, db_index=True)

    price = models.IntegerField(_('価格'), default=0)
    memo = models.TextField(_('備考'), blank=True, null=True, default='ここに備考を記入してください。')
    temporary_booked_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # Phase 4b: メール予約対応
    booking_channel = models.CharField(
        _('予約経路'), max_length=10,
        choices=[('line', 'LINE'), ('email', 'Email')],
        default='line',
    )
    customer_email = models.EmailField(_('顧客メール'), blank=True, null=True)
    email_otp_hash = models.CharField(_('OTPハッシュ'), max_length=64, blank=True, null=True)
    email_otp_expires = models.DateTimeField(_('OTP有効期限'), blank=True, null=True)
    email_verified = models.BooleanField(_('メール認証済み'), default=False)
    payment_url = models.URLField(_('決済URL'), blank=True, null=True)

    # QRチェックイン
    checkin_qr = models.ImageField(_('チェックインQR'), upload_to='checkin_qr/', blank=True, null=True)
    is_checked_in = models.BooleanField(_('チェックイン済み'), default=False)
    checked_in_at = models.DateTimeField(_('チェックイン日時'), blank=True, null=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('予約確定済みのスケジュール')
        verbose_name_plural = _('確定予約一覧')
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
    title = models.CharField(max_length=200)
    link = models.URLField()
    content = models.TextField(default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('お知らせ')
        verbose_name_plural = _('お知らせ')

    def __str__(self):
        return self.title


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


class IoTDevice(models.Model):
    """Pico + センサーを含む IoT デバイス情報"""
    DEVICE_TYPE_CHOICES = [
        ('multi', 'マルチセンサーノード'),
        ('door', 'スマートロック'),
        ('other', 'その他'),
    ]

    name = models.CharField(_('デバイス名'), max_length=100)
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='iot_devices')
    device_type = models.CharField(_('種別'), choices=DEVICE_TYPE_CHOICES, max_length=20, default='multi')

    external_id = models.CharField(_('デバイスID（AWS側）'), max_length=255, unique=True)
    api_key_hash = models.CharField(_('APIキーハッシュ'), max_length=64, db_index=True, default='',
                                     help_text=_('SHA-256ハッシュ。認証時の照合用'))
    api_key_prefix = models.CharField(_('APIキープレフィックス'), max_length=8, blank=True, default='',
                                       help_text=_('管理画面表示用（先頭8文字）'))

    mq9_threshold = models.FloatField(_('MQ-9閾値'), null=True, blank=True)
    alert_enabled = models.BooleanField(_('ガス検知アラート有効'), default=False)
    alert_email = models.EmailField(_('アラート送信メール'), blank=True)
    alert_line_user_id = models.CharField(
        _('アラートLINE通知先ID'), max_length=255, blank=True, default='',
        help_text=_('閾値超過時にLINE通知を送信するユーザーID')
    )

    wifi_ssid = models.CharField(_('Wi-Fi SSID'), max_length=64, blank=True)
    wifi_password_enc = models.CharField(_('Wi-Fi パスワード（暗号化）'), max_length=512, blank=True)
    pending_ir_command = models.TextField(_('保留中IRコマンド'), blank=True, default='',
        help_text=_('デバイスが次回config取得時に実行するIRコマンド（JSON）')
    )

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

    is_active = models.BooleanField(_('有効'), default=True)
    last_seen_at = models.DateTimeField(_('最終通信日時'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('店舗センサー')
        verbose_name_plural = _('店舗センサー')

    def __str__(self):
        return f'{self.store.name} / {self.name}'


class IoTEvent(models.Model):
    """IoT デバイスから送信されたセンサーログ"""
    device = models.ForeignKey(IoTDevice, verbose_name=_('デバイス'), on_delete=models.CASCADE, related_name='events')
    created_at = models.DateTimeField(_('受信日時'), auto_now_add=True, db_index=True)
    event_type = models.CharField(_('イベント種別'), max_length=50, blank=True)
    payload = models.TextField(_('ペイロード(JSON)'), blank=True)
    mq9_value = models.FloatField(_('MQ-9値'), null=True, blank=True, db_index=True)
    light_value = models.FloatField(_('照度値'), null=True, blank=True, db_index=True)
    sound_value = models.FloatField(_('音値'), null=True, blank=True, db_index=True)
    pir_triggered = models.BooleanField(_('PIR検知'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('IoTイベントログ')
        verbose_name_plural = _('IoTイベントログ')
        indexes = [
            models.Index(fields=['device', 'created_at']),
            models.Index(fields=['device', 'mq9_value', 'created_at']),
            models.Index(fields=['device', 'created_at', 'light_value']),
            models.Index(fields=['device', 'created_at', 'sound_value']),
        ]

    def __str__(self):
        return f'{self.device} @ {self.created_at}'


class VentilationAutoControl(models.Model):
    """CO閾値連動 換気扇自動制御ルール（SwitchBot スマートプラグ経由）"""
    device = models.ForeignKey(IoTDevice, verbose_name=_('対象デバイス'),
                               on_delete=models.CASCADE, related_name='ventilation_rules')
    name = models.CharField(_('ルール名'), max_length=100, default='換気扇自動制御')
    is_active = models.BooleanField(_('有効'), default=True)

    # 閾値設定（生ADC値）
    threshold_on = models.IntegerField(_('ON閾値（MQ-9 ADC値）'), default=400,
        help_text=_('この値を連続で超えたら換気扇ON'))
    threshold_off = models.IntegerField(_('OFF閾値（MQ-9 ADC値）'), default=200,
        help_text=_('この値以下になったら換気扇OFF'))
    consecutive_count = models.IntegerField(_('連続超過回数'), default=3,
        help_text=_('ON閾値をこの回数連続で超えたらON実行（20秒間隔×3=約1分）'))

    # SwitchBot設定（暗号化保存）
    switchbot_token = models.CharField(_('SwitchBotトークン（暗号化）'), max_length=500, blank=True, default='')
    switchbot_secret = models.CharField(_('SwitchBotシークレット（暗号化）'), max_length=500, blank=True, default='')
    switchbot_device_id = models.CharField(_('SwitchBotデバイスID'), max_length=100,
        help_text=_('スマートプラグのデバイスID'))

    # 状態トラッキング
    fan_state = models.CharField(_('現在の状態'), max_length=10,
        choices=[('off', 'OFF'), ('on', 'ON'), ('unknown', '不明')], default='unknown')
    last_on_at = models.DateTimeField(_('最後にONした日時'), null=True, blank=True)
    last_off_at = models.DateTimeField(_('最後にOFFした日時'), null=True, blank=True)
    cooldown_seconds = models.IntegerField(_('クールダウン（秒）'), default=60,
        help_text=_('ON/OFF切替後、次の切替までの最小待機時間'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('換気扇自動制御')
        verbose_name_plural = _('換気扇自動制御')

    def __str__(self):
        return f'{self.name} ({self.device.name})'

    @staticmethod
    def _get_fernet():
        """IOT_ENCRYPTION_KEY を使ったFernetインスタンスを返す"""
        key = getattr(settings, 'IOT_ENCRYPTION_KEY', None)
        if not key or not Fernet:
            raise ImproperlyConfigured("IOT_ENCRYPTION_KEY is not set or cryptography not installed")
        return Fernet(key.encode('utf-8') if isinstance(key, str) else key)

    def set_switchbot_token(self, plain_token: str) -> None:
        if not plain_token:
            self.switchbot_token = ''
            return
        f = self._get_fernet()
        self.switchbot_token = f.encrypt(plain_token.encode('utf-8')).decode('utf-8')

    def get_switchbot_token(self) -> Optional[str]:
        if not self.switchbot_token:
            return None
        try:
            f = self._get_fernet()
            return f.decrypt(self.switchbot_token.encode('utf-8')).decode('utf-8')
        except Exception:
            return self.switchbot_token  # fallback: 未暗号化の値

    def set_switchbot_secret(self, plain_secret: str) -> None:
        if not plain_secret:
            self.switchbot_secret = ''
            return
        f = self._get_fernet()
        self.switchbot_secret = f.encrypt(plain_secret.encode('utf-8')).decode('utf-8')

    def get_switchbot_secret(self) -> Optional[str]:
        if not self.switchbot_secret:
            return None
        try:
            f = self._get_fernet()
            return f.decrypt(self.switchbot_secret.encode('utf-8')).decode('utf-8')
        except Exception:
            return self.switchbot_secret  # fallback: 未暗号化の値


class IRCode(models.Model):
    """学習済みIRリモコンコード"""
    device = models.ForeignKey(IoTDevice, verbose_name=_('デバイス'), on_delete=models.CASCADE, related_name='ir_codes')
    name = models.CharField(_('名前'), max_length=100)
    protocol = models.CharField(_('プロトコル'), max_length=20, default='NEC')
    code = models.CharField(_('コード'), max_length=20)
    address = models.CharField(_('アドレス'), max_length=20, blank=True, default='')
    command = models.CharField(_('コマンド'), max_length=20, blank=True, default='')
    raw_data = models.TextField(_('RAWデータ'), blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('IRコード')
        verbose_name_plural = _('IRコード')

    def __str__(self):
        return f'{self.device.name} / {self.name}'


# ==============================
# 追加: 在庫 / 注文 / 入庫QR / 翻訳
# ==============================

class Category(models.Model):
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(_('カテゴリ名'), max_length=100)
    sort_order = models.IntegerField(_('並び順'), default=0)

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


class Order(models.Model):
    """注文（セッション/会計単位のかたまり）"""

    STATUS_OPEN = 'OPEN'
    STATUS_CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (STATUS_OPEN, 'Open'),
        (STATUS_CLOSED, 'Closed'),
    )
    PAYMENT_STATUS_CHOICES = [
        ('pending', '未払い'),
        ('partial', '一部支払'),
        ('paid', '支払済'),
        ('refunded', '返金済'),
    ]
    CHANNEL_CHOICES = [
        ('ec', 'ECショップ'),
        ('pos', 'POS'),
        ('table', 'テーブル注文'),
        ('reservation', '予約'),
    ]

    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='orders')
    schedule = models.ForeignKey(
        Schedule,
        verbose_name=_('予約'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders'
    )

    channel = models.CharField(_('注文チャネル'), max_length=20, choices=CHANNEL_CHOICES, default='pos', db_index=True)
    customer_line_user_hash = models.CharField(_('顧客LINEハッシュ'), max_length=64, null=True, blank=True, db_index=True)
    table_label = models.CharField(_('席/テーブル'), max_length=50, blank=True, default='')
    table_seat = models.ForeignKey(
        'TableSeat', verbose_name=_('席'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='orders',
    )

    status = models.CharField(_('状態'), max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN, db_index=True)
    payment_status = models.CharField(_('支払状態'), max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    discount_amount = models.IntegerField(_('割引額'), default=0)
    tax_amount = models.IntegerField(_('税額'), default=0)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('注文履歴')
        verbose_name_plural = _('注文履歴')
        indexes = [
            models.Index(fields=['store', 'status', 'created_at']),
            models.Index(fields=['customer_line_user_hash', 'created_at']),
        ]

    def __str__(self):
        return f"Order#{self.id} {self.store.name} ({self.status})"

    @property
    def all_items_served(self):
        """全アイテムが配膳済みかどうか"""
        items = self.items.all()
        return items.exists() and all(i.status == 'SERVED' for i in items)


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

    order = models.ForeignKey(Order, verbose_name=_('注文'), on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, verbose_name=_('商品'), on_delete=models.PROTECT, related_name='order_items')

    qty = models.IntegerField(_('数量'), default=1)
    unit_price = models.IntegerField(_('単価'), default=0)

    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default=STATUS_ORDERED, db_index=True)
    note = models.CharField(_('備考'), max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('注文明細')
        verbose_name_plural = _('注文明細')
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

    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, verbose_name=_('商品'), on_delete=models.PROTECT, related_name='stock_movements')

    movement_type = models.CharField(_('種別'), max_length=10, choices=TYPE_CHOICES, db_index=True)
    qty = models.IntegerField(_('数量'))

    by_staff = models.ForeignKey(Staff, verbose_name=_('実施スタッフ'), on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(_('メモ'), max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('入出庫履歴')
        verbose_name_plural = _('入出庫履歴')
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
        ('info', '情報'),
        ('warning', '注意'),
        ('critical', '重要'),
    ]
    CATEGORY_CHOICES = [
        ('sales', '売上'),
        ('inventory', '在庫'),
        ('staffing', 'スタッフ'),
        ('menu', 'メニュー'),
        ('customer', '顧客'),
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
        ('positive', 'ポジティブ'),
        ('neutral', 'ニュートラル'),
        ('negative', 'ネガティブ'),
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


# ==============================
# Phase 2: デバッグ / ランタイム設定
# ==============================

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

    name = models.CharField(_('物件名'), max_length=200)
    address = models.CharField(_('住所'), max_length=300)
    property_type = models.CharField(_('種別'), max_length=20, choices=PROPERTY_TYPE_CHOICES, default='apartment')
    owner_name = models.CharField(_('オーナー名'), max_length=100, blank=True)
    owner_contact = models.CharField(_('オーナー連絡先'), max_length=200, blank=True)
    store = models.ForeignKey(
        Store, verbose_name=_('関連店舗'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='properties',
    )
    is_active = models.BooleanField(_('有効'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('物件')
        verbose_name_plural = _('物件')

    def __str__(self):
        return self.name


class PropertyDevice(models.Model):
    """物件に設置されたデバイス"""
    property = models.ForeignKey(
        Property, verbose_name=_('物件'), on_delete=models.CASCADE, related_name='property_devices',
    )
    device = models.ForeignKey(
        IoTDevice, verbose_name=_('デバイス'), on_delete=models.CASCADE, related_name='property_placements',
    )
    location_label = models.CharField(_('設置場所'), max_length=100, help_text=_('例: リビング, 玄関, 寝室'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('物件デバイス')
        verbose_name_plural = _('物件デバイス')
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
        Property, verbose_name=_('物件'), on_delete=models.CASCADE, related_name='alerts',
    )
    device = models.ForeignKey(
        IoTDevice, verbose_name=_('デバイス'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='property_alerts',
    )
    alert_type = models.CharField(_('種別'), max_length=20, choices=ALERT_TYPE_CHOICES)
    severity = models.CharField(_('重要度'), max_length=10, choices=SEVERITY_CHOICES, default='info')
    message = models.TextField(_('メッセージ'), blank=True)
    is_resolved = models.BooleanField(_('解決済み'), default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(_('解決日時'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('物件アラート')
        verbose_name_plural = _('物件アラート')
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
    open_hour = models.IntegerField(_('営業開始時間'), default=9)      # 0-23
    close_hour = models.IntegerField(_('営業終了時間'), default=21)     # 0-23
    slot_duration = models.IntegerField(_('予約コマ(分)'), default=60,
        help_text=_('15, 30, 45, 60 のいずれか'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('店舗スケジュール設定')
        verbose_name_plural = _('店舗スケジュール設定')

    def __str__(self):
        return f"{self.store.name} ({self.open_hour}:00-{self.close_hour}:00 / {self.slot_duration}分)"


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


class PaymentMethod(models.Model):
    """店舗別決済方法設定"""
    METHOD_TYPE_CHOICES = [
        ('cash', '現金'),
        ('coiney', 'Coiney (クレジットカード)'),
        ('paypay', 'PayPay'),
        ('ic', 'IC決済 (交通系/電子マネー)'),
        ('other', 'その他'),
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


class ShiftPeriod(models.Model):
    """マネージャーが作成するシフト募集期間（3ヶ月分など）"""
    STATUS_CHOICES = [
        ('open', '募集中'),
        ('closed', '締切'),
        ('scheduled', 'スケジュール済'),
        ('approved', '承認済'),
    ]
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name='shift_periods')
    year_month = models.DateField(_('対象年月'))  # 月初の日付
    deadline = models.DateTimeField(_('申請締切'))
    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default='open')
    created_by = models.ForeignKey(Staff, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト募集期間')
        verbose_name_plural = _('シフト募集期間')

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
    date = models.DateField(_('日付'))
    start_hour = models.IntegerField(_('開始時間'))
    end_hour = models.IntegerField(_('終了時間'))
    start_time = models.TimeField(_('開始時刻'), null=True, blank=True)
    end_time = models.TimeField(_('終了時刻'), null=True, blank=True)
    preference = models.CharField(_('希望区分'), max_length=20, choices=PREF_CHOICES, default='available')
    note = models.TextField(_('備考'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト希望')
        verbose_name_plural = _('シフト希望')
        unique_together = ('period', 'staff', 'date', 'start_hour')

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00 ({self.get_preference_display()})"


class ShiftAssignment(models.Model):
    """確定シフト"""
    period = models.ForeignKey(ShiftPeriod, on_delete=models.CASCADE, related_name='assignments')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='shift_assignments')
    date = models.DateField(_('日付'))
    start_hour = models.IntegerField(_('開始時間'))
    end_hour = models.IntegerField(_('終了時間'))
    start_time = models.TimeField(_('開始時刻'), null=True, blank=True)
    end_time = models.TimeField(_('終了時刻'), null=True, blank=True)
    color = models.CharField(_('表示色'), max_length=7, default='#3B82F6')
    note = models.TextField(_('備考'), blank=True, default='')
    is_synced = models.BooleanField(_('Schedule同期済み'), default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('確定シフト')
        verbose_name_plural = _('確定シフト')
        unique_together = ('period', 'staff', 'date', 'start_hour')

    def __str__(self):
        return f"{self.staff.name} {self.date} {self.start_hour}:00-{self.end_hour}:00"


class ShiftTemplate(models.Model):
    """定型シフトパターン（早番・遅番・通し等）"""
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='shift_templates')
    name = models.CharField(_('テンプレート名'), max_length=100)
    start_time = models.TimeField(_('開始時刻'))
    end_time = models.TimeField(_('終了時刻'))
    color = models.CharField(_('表示色'), max_length=7, default='#3B82F6')
    is_active = models.BooleanField(_('有効'), default=True)
    sort_order = models.IntegerField(_('並び順'), default=0)

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフトテンプレート')
        verbose_name_plural = _('シフトテンプレート')
        ordering = ('store', 'sort_order', 'name')

    def __str__(self):
        return f"{self.store.name} / {self.name} ({self.start_time}-{self.end_time})"


class ShiftPublishHistory(models.Model):
    """シフト公開履歴"""
    period = models.ForeignKey(ShiftPeriod, verbose_name=_('シフト期間'), on_delete=models.CASCADE, related_name='publish_history')
    published_by = models.ForeignKey(Staff, verbose_name=_('公開者'), on_delete=models.SET_NULL, null=True, blank=True)
    published_at = models.DateTimeField(_('公開日時'), auto_now_add=True)
    assignment_count = models.IntegerField(_('シフト数'), default=0)
    note = models.TextField(_('備考'), blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('シフト公開履歴')
        verbose_name_plural = _('シフト公開履歴')
        ordering = ('-published_at',)

    def __str__(self):
        return f"{self.period} - {self.published_at}"


class AdminTheme(models.Model):
    """管理画面UIカスタムテーマ"""
    store = models.OneToOneField(Store, on_delete=models.CASCADE, related_name='admin_theme')
    primary_color = models.CharField(_('メインカラー'), max_length=7, default='#8c876c')
    secondary_color = models.CharField(_('サブカラー'), max_length=7, default='#f1f0ec')
    header_image = models.ImageField(_('ヘッダー画像'), upload_to='admin_themes/', blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('管理画面テーマ')
        verbose_name_plural = _('管理画面テーマ')

    def __str__(self):
        return f"{self.store.name} テーマ"


# ==============================
# Round 4: ホームページCMS
# ==============================

class SiteSettings(models.Model):
    """サイト全体の設定 (シングルトン)"""
    site_name = models.CharField(_('サイト名'), max_length=200, default='占いサロンチャンス')

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

    # AIチャットウィジェット
    show_ai_chat = models.BooleanField(_('AIアシスタント表示'), default=False,
        help_text=_('フロントページにAIアシスタントチャットを表示するかどうか'))

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


class HomepageCustomBlock(models.Model):
    """WordPress風カスタムHTMLブロック"""
    POSITION_CHOICES = [
        ('above_cards', 'カードの上'),
        ('below_cards', 'カードの下'),
        ('sidebar', 'サイドバー'),
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
        ('after_hero', 'ヒーローバナーの後'),
        ('after_cards', 'カードの後'),
        ('after_ranking', 'ランキングの後'),
        ('after_campaign', 'キャンペーンの後'),
        ('sidebar', 'サイドバー'),
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
        Staff, verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='employment_contract',
    )
    employment_type = models.CharField(_('雇用形態'), max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='part_time')
    pay_type = models.CharField(_('給与形態'), max_length=10, choices=PAY_TYPE_CHOICES, default='hourly')
    hourly_rate = models.IntegerField(_('時給（円）'), default=0, help_text=_('時給制の場合に設定'))
    monthly_salary = models.IntegerField(_('月給（円）'), default=0, help_text=_('月給制の場合に設定'))

    commute_allowance = models.IntegerField(_('通勤手当（円/月）'), default=0)
    housing_allowance = models.IntegerField(_('住宅手当（円/月）'), default=0)
    family_allowance = models.IntegerField(_('家族手当（円/月）'), default=0)

    standard_monthly_remuneration = models.IntegerField(
        _('標準報酬月額（円）'), default=0,
        help_text=_('社会保険料計算の基準額。4〜6月の平均報酬から算定。'),
    )
    resident_tax_monthly = models.IntegerField(_('住民税月額（円）'), default=0, help_text=_('特別徴収の月額'))

    birth_date = models.DateField(_('生年月日'), null=True, blank=True, help_text=_('介護保険適用判定に使用（40歳以上）'))
    contract_start = models.DateField(_('契約開始日'), null=True, blank=True)
    contract_end = models.DateField(_('契約終了日'), null=True, blank=True)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('雇用契約')
        verbose_name_plural = _('雇用契約')

    def __str__(self):
        return f'{self.staff.name} ({self.get_employment_type_display()} / {self.get_pay_type_display()})'


class WorkAttendance(models.Model):
    """勤怠記録"""
    SOURCE_CHOICES = [
        ('shift', 'シフトから自動生成'),
        ('manual', '手動入力'),
        ('corrected', '修正済み'),
        ('qr', 'QR打刻'),
    ]

    staff = models.ForeignKey(Staff, verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(_('日付'), db_index=True)
    clock_in = models.TimeField(_('出勤時刻'), null=True, blank=True)
    clock_out = models.TimeField(_('退勤時刻'), null=True, blank=True)

    regular_minutes = models.IntegerField(_('通常勤務（分）'), default=0)
    overtime_minutes = models.IntegerField(_('残業（分）'), default=0)
    late_night_minutes = models.IntegerField(_('深夜勤務（分）'), default=0)
    holiday_minutes = models.IntegerField(_('休日勤務（分）'), default=0)
    break_minutes = models.IntegerField(_('休憩（分）'), default=0)

    qr_clock_in = models.DateTimeField(_('QR出勤日時'), null=True, blank=True)
    qr_clock_out = models.DateTimeField(_('QR退勤日時'), null=True, blank=True)

    source = models.CharField(_('データソース'), max_length=20, choices=SOURCE_CHOICES, default='shift')
    source_assignment = models.ForeignKey(
        ShiftAssignment, verbose_name=_('元シフト'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='derived_attendances',
    )

    class Meta:
        app_label = 'booking'
        verbose_name = _('勤怠記録')
        verbose_name_plural = _('勤怠記録')
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

    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='payroll_periods')
    year_month = models.CharField(_('対象年月'), max_length=7, help_text=_('YYYY-MM形式'))
    period_start = models.DateField(_('計算期間開始'))
    period_end = models.DateField(_('計算期間終了'))
    status = models.CharField(_('状態'), max_length=20, choices=STATUS_CHOICES, default='draft')
    payment_date = models.DateField(_('支給日'), null=True, blank=True)
    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与計算期間')
        verbose_name_plural = _('給与計算期間')
        unique_together = ('store', 'year_month')

    def __str__(self):
        return f'{self.store.name} {self.year_month} ({self.get_status_display()})'


class PayrollEntry(models.Model):
    """個人別給与明細"""
    period = models.ForeignKey(PayrollPeriod, verbose_name=_('給与期間'), on_delete=models.CASCADE, related_name='entries')
    staff = models.ForeignKey(Staff, verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='payroll_entries')
    contract = models.ForeignKey(
        EmploymentContract, verbose_name=_('雇用契約'), on_delete=models.SET_NULL,
        null=True, blank=True, related_name='payroll_entries',
    )

    total_work_days = models.IntegerField(_('出勤日数'), default=0)
    total_regular_hours = models.DecimalField(_('通常勤務時間'), max_digits=6, decimal_places=2, default=0)
    total_overtime_hours = models.DecimalField(_('残業時間'), max_digits=6, decimal_places=2, default=0)
    total_late_night_hours = models.DecimalField(_('深夜勤務時間'), max_digits=6, decimal_places=2, default=0)
    total_holiday_hours = models.DecimalField(_('休日勤務時間'), max_digits=6, decimal_places=2, default=0)

    base_pay = models.IntegerField(_('基本給'), default=0)
    overtime_pay = models.IntegerField(_('残業手当'), default=0)
    late_night_pay = models.IntegerField(_('深夜手当'), default=0)
    holiday_pay = models.IntegerField(_('休日手当'), default=0)
    allowances = models.IntegerField(_('各種手当合計'), default=0, help_text=_('通勤+住宅+家族手当'))

    gross_pay = models.IntegerField(_('総支給額'), default=0)
    total_deductions = models.IntegerField(_('控除合計'), default=0)
    net_pay = models.IntegerField(_('差引支給額'), default=0)

    created_at = models.DateTimeField(_('作成日時'), auto_now_add=True)
    updated_at = models.DateTimeField(_('更新日時'), auto_now=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与明細')
        verbose_name_plural = _('給与明細')
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

    entry = models.ForeignKey(PayrollEntry, verbose_name=_('給与明細'), on_delete=models.CASCADE, related_name='deductions')
    deduction_type = models.CharField(_('控除種別'), max_length=30, choices=DEDUCTION_TYPE_CHOICES)
    amount = models.IntegerField(_('金額'), default=0)
    is_employer_only = models.BooleanField(_('事業主負担のみ'), default=False, help_text=_('労災保険等、従業員控除なし'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('控除明細')
        verbose_name_plural = _('控除明細')

    def __str__(self):
        label = self.get_deduction_type_display()
        return f'{label}: {self.amount:,}円'


class SalaryStructure(models.Model):
    """給与体系（Store 1:1）— 社会保険料率・割増率"""
    store = models.OneToOneField(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='salary_structure')

    # 社会保険料率（従業員負担分、%表記→小数で格納）
    pension_rate = models.DecimalField(_('厚生年金料率(%)'), max_digits=5, decimal_places=3, default=Decimal('9.150'),
        help_text=_('従業員負担分 例: 9.150'))
    health_insurance_rate = models.DecimalField(_('健康保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('5.000'),
        help_text=_('従業員負担分 例: 5.000（協会けんぽ東京支部）'))
    employment_insurance_rate = models.DecimalField(_('雇用保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.600'),
        help_text=_('従業員負担分 例: 0.600'))
    long_term_care_rate = models.DecimalField(_('介護保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.820'),
        help_text=_('40歳以上のみ適用 例: 0.820'))
    workers_comp_rate = models.DecimalField(_('労災保険料率(%)'), max_digits=5, decimal_places=3, default=Decimal('0.300'),
        help_text=_('事業主全額負担（記録用） 例: 0.300'))

    # 割増率
    overtime_multiplier = models.DecimalField(_('残業割増率'), max_digits=4, decimal_places=2, default=Decimal('1.25'))
    late_night_multiplier = models.DecimalField(_('深夜割増率'), max_digits=4, decimal_places=2, default=Decimal('1.35'))
    holiday_multiplier = models.DecimalField(_('休日割増率'), max_digits=4, decimal_places=2, default=Decimal('1.50'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('給与体系')
        verbose_name_plural = _('給与体系')

    def __str__(self):
        return f'{self.store.name} 給与体系'


# ==============================
# セキュリティ監査・監視ログ・AWSコスト
# ==============================

class SecurityAudit(models.Model):
    """セキュリティ監査結果"""
    SEVERITY_CHOICES = [
        ('critical', '重大'),
        ('high', '高'),
        ('medium', '中'),
        ('low', '低'),
        ('info', '情報'),
        ('pass', '合格'),
    ]
    STATUS_CHOICES = [
        ('fail', '不合格'),
        ('warn', '警告'),
        ('pass', '合格'),
    ]
    CATEGORY_CHOICES = [
        ('django_settings', 'Django設定'),
        ('credentials', '認証情報'),
        ('endpoints', 'エンドポイント'),
        ('infrastructure', 'インフラ'),
        ('dependencies', '依存関係'),
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
        ('login_success', 'ログイン成功'),
        ('login_fail', 'ログイン失敗'),
        ('api_auth_fail', 'API認証失敗'),
        ('permission_denied', '権限拒否'),
        ('suspicious_request', '不審なリクエスト'),
        ('admin_action', '管理操作'),
    ]
    SEVERITY_CHOICES = [
        ('critical', '緊急'),
        ('warning', '警告'),
        ('info', '情報'),
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
        ('ok', 'OK'),
        ('warn', '警告'),
        ('alert', 'アラート'),
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
        ('developer', '開発者'),
        ('owner', 'オーナー'),
        ('manager', '店長'),
        ('staff', 'スタッフ'),
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


# ==============================
# Phase 2: QR TOTP 勤怠
# ==============================

class AttendanceTOTPConfig(models.Model):
    """店舗ごとのTOTP設定（QR勤怠用）"""
    store = models.OneToOneField(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='totp_config')
    totp_secret = models.CharField(_('TOTPシークレット'), max_length=64)
    totp_interval = models.IntegerField(_('TOTP間隔(秒)'), default=30)
    location_lat = models.FloatField(_('緯度'), null=True, blank=True)
    location_lng = models.FloatField(_('経度'), null=True, blank=True)
    geo_fence_radius_m = models.IntegerField(_('ジオフェンス半径(m)'), default=200)
    require_geo_check = models.BooleanField(_('位置確認必須'), default=False)
    is_active = models.BooleanField(_('有効'), default=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('TOTP勤怠設定')
        verbose_name_plural = _('TOTP勤怠設定')

    def __str__(self):
        return f'{self.store.name} TOTP設定'


class AttendanceStamp(models.Model):
    """打刻ログ"""
    STAMP_TYPE_CHOICES = [
        ('clock_in', '出勤'),
        ('clock_out', '退勤'),
        ('break_start', '休憩開始'),
        ('break_end', '休憩終了'),
    ]
    staff = models.ForeignKey(Staff, verbose_name=_('スタッフ'), on_delete=models.CASCADE, related_name='attendance_stamps')
    stamp_type = models.CharField(_('打刻種別'), max_length=20, choices=STAMP_TYPE_CHOICES)
    stamped_at = models.DateTimeField(_('打刻日時'), auto_now_add=True)
    totp_used = models.CharField(_('使用TOTP'), max_length=10, blank=True, default='')
    ip_address = models.GenericIPAddressField(_('IPアドレス'), null=True, blank=True)
    user_agent = models.TextField(_('User-Agent'), blank=True, default='')
    latitude = models.FloatField(_('緯度'), null=True, blank=True)
    longitude = models.FloatField(_('経度'), null=True, blank=True)
    is_valid = models.BooleanField(_('有効'), default=True)
    invalidation_reason = models.CharField(_('無効理由'), max_length=100, blank=True, default='')

    class Meta:
        app_label = 'booking'
        verbose_name = _('打刻ログ')
        verbose_name_plural = _('打刻ログ')
        ordering = ('-stamped_at',)
        indexes = [
            models.Index(fields=['staff', 'stamped_at']),
            models.Index(fields=['stamp_type', 'stamped_at']),
        ]

    def __str__(self):
        return f'{self.staff.name} {self.get_stamp_type_display()} {self.stamped_at}'


# ==============================
# Phase 3: POS拡張
# ==============================

class POSTransaction(models.Model):
    """POS決済記録"""
    order = models.OneToOneField(Order, verbose_name=_('注文'), on_delete=models.CASCADE, related_name='pos_transaction')
    payment_method = models.ForeignKey(PaymentMethod, verbose_name=_('決済方法'), on_delete=models.SET_NULL, null=True, blank=True)
    total_amount = models.IntegerField(_('合計金額'), default=0)
    tax_amount = models.IntegerField(_('税額'), default=0)
    discount_amount = models.IntegerField(_('割引額'), default=0)
    cash_received = models.IntegerField(_('受取金額'), null=True, blank=True)
    change_given = models.IntegerField(_('お釣り'), null=True, blank=True)
    receipt_number = models.CharField(_('レシート番号'), max_length=20, unique=True)
    staff = models.ForeignKey(Staff, verbose_name=_('担当'), on_delete=models.SET_NULL, null=True, blank=True)
    completed_at = models.DateTimeField(_('完了日時'), null=True, blank=True)

    class Meta:
        app_label = 'booking'
        verbose_name = _('POS決済履歴')
        verbose_name_plural = _('POS決済履歴')
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['completed_at']),
        ]

    def __str__(self):
        return f'POS#{self.receipt_number} ¥{self.total_amount:,}'


# ==============================
# Phase 4: 来客分析
# ==============================

class VisitorCount(models.Model):
    """時間帯別来客集計"""
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='visitor_counts')
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
    store = models.OneToOneField(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='visitor_config')
    pir_device = models.ForeignKey(IoTDevice, verbose_name=_('PIRデバイス'), on_delete=models.SET_NULL, null=True, blank=True)
    session_gap_seconds = models.IntegerField(_('セッション間隔(秒)'), default=300,
        help_text=_('この秒数以内の連続検知は同一来客とカウント'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('来客分析設定')
        verbose_name_plural = _('来客分析設定')

    def __str__(self):
        return f'{self.store.name} 来客分析設定'


# ==============================
# Phase 5: AIシフト推薦
# ==============================

class StaffRecommendationModel(models.Model):
    """学習済みMLモデル保存"""
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_models')
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
    store = models.ForeignKey(Store, verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='recommendation_results')
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