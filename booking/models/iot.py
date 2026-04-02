"""IoT models: IoTDevice, IoTEvent, VentilationAutoControl, IRCode, Property."""
import hashlib
import logging
from typing import Optional

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


class IoTDevice(models.Model):
    """Pico + センサーを含む IoT デバイス情報"""
    DEVICE_TYPE_CHOICES = [
        ('multi', _('マルチセンサーノード')),
        ('door', _('スマートロック')),
        ('other', _('その他')),
    ]

    name = models.CharField(_('デバイス名'), max_length=100)
    store = models.ForeignKey('Store', verbose_name=_('店舗'), on_delete=models.CASCADE, related_name='iot_devices')
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
        choices=[('off', _('OFF')), ('on', _('ON')), ('unknown', _('不明'))], default='unknown')
    last_on_at = models.DateTimeField(_('最後にONした日時'), null=True, blank=True)
    last_off_at = models.DateTimeField(_('最後にOFFした日時'), null=True, blank=True)
    cooldown_seconds = models.IntegerField(_('クールダウン（秒）'), default=60,
        help_text=_('ON/OFF切替後、次の切替までの最小待機時間'))

    class Meta:
        app_label = 'booking'
        verbose_name = _('自動制御')
        verbose_name_plural = _('自動制御')

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
            logger.error("Failed to decrypt switchbot_token for rule %s", self.pk)
            return None

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
            logger.error("Failed to decrypt switchbot_secret for rule %s", self.pk)
            return None


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


class Property(models.Model):
    """物件情報"""
    PROPERTY_TYPE_CHOICES = [
        ('apartment', _('アパート/マンション')),
        ('house', _('一戸建て')),
        ('office', _('オフィス')),
        ('store', _('店舗')),
    ]

    name = models.CharField(_('物件名'), max_length=200)
    address = models.CharField(_('住所'), max_length=300)
    property_type = models.CharField(_('種別'), max_length=20, choices=PROPERTY_TYPE_CHOICES, default='apartment')
    owner_name = models.CharField(_('オーナー名'), max_length=100, blank=True)
    owner_contact = models.CharField(_('オーナー連絡先'), max_length=200, blank=True)
    store = models.ForeignKey(
        'Store', verbose_name=_('関連店舗'), on_delete=models.SET_NULL,
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
        ('gas_leak', _('ガス漏れ')),
        ('no_motion', _('長期不在')),
        ('device_offline', _('デバイスオフライン')),
        ('custom', _('カスタム')),
    ]
    SEVERITY_CHOICES = [
        ('critical', _('緊急')),
        ('warning', _('警告')),
        ('info', _('情報')),
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
