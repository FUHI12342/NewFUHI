"""Schedule model for booking reservations."""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ImproperlyConfigured

import secrets
import string
import uuid
import hashlib
from typing import Optional

try:
    from cryptography.fernet import Fernet
except Exception:  # pragma: no cover
    Fernet = None


class Schedule(models.Model):
    """予約スケジュール."""
    reservation_number = models.CharField(
        _('予約番号'),
        max_length=36,
        default=uuid.uuid4,
        editable=False,
        db_index=True,
    )
    start = models.DateTimeField(_('開始時間'), db_index=True)
    end = models.DateTimeField(_('終了時間'))
    staff = models.ForeignKey('Staff', verbose_name=_('キャスト'), on_delete=models.CASCADE, db_index=True)
    store = models.ForeignKey(
        'Store', verbose_name=_('予約店舗'),
        on_delete=models.CASCADE, null=True, blank=True,
        related_name='schedules',
        help_text=_('未設定の場合はスタッフの主店舗'),
    )

    customer_name = models.CharField(_('予約者名'), max_length=255, null=True, blank=True)
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

    # 埋め込み予約フロー用トークン
    embed_token = models.CharField(
        _('埋め込みトークン'), max_length=43,
        unique=True, null=True, blank=True, db_index=True,
    )

    # 顧客キャンセル用トークン
    cancel_token = models.CharField(
        _('キャンセル番号'), max_length=8,
        unique=True, null=True, blank=True,
        help_text=_('顧客キャンセル用8桁コード'),
    )

    # 返金追跡
    refund_status = models.CharField(
        _('返金ステータス'), max_length=20,
        choices=[
            ('none', _('返金不要')),
            ('pending', _('返金待ち')),
            ('completed', _('返金済み')),
        ],
        default='none',
    )
    refund_completed_at = models.DateTimeField(
        _('返金完了日時'), blank=True, null=True,
    )
    refund_completed_by = models.ForeignKey(
        'Staff', verbose_name=_('返金処理者'),
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='refunds_processed',
    )
    refund_note = models.TextField(_('返金備考'), blank=True, default='')

    # QRチェックイン
    checkin_qr = models.ImageField(_('チェックインQR'), upload_to='checkin_qr/', blank=True, null=True)
    is_checked_in = models.BooleanField(_('チェックイン済み'), default=False)
    checked_in_at = models.DateTimeField(_('チェックイン日時'), blank=True, null=True)
    checkin_backup_code = models.CharField(
        _('バックアップコード'), max_length=6,
        blank=True, null=True,
        help_text=_('口頭確認用6桁コード'),
    )
    checked_in_by = models.ForeignKey(
        'Staff', verbose_name=_('チェックイン担当'),
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='checkins_performed',
    )

    # LINEリマインダー
    reminder_sent_day_before = models.BooleanField(_('前日リマインダー送信済み'), default=False)
    reminder_sent_same_day = models.BooleanField(_('当日リマインダー送信済み'), default=False)

    # 仮予約確認フロー
    CONFIRMATION_CHOICES = [
        ('none', _('通常')),
        ('pending', _('確認待ち')),
        ('confirmed', _('確定')),
        ('rejected', _('却下')),
    ]
    confirmation_status = models.CharField(
        _('確認ステータス'), max_length=20,
        choices=CONFIRMATION_CHOICES, default='none',
    )
    confirmed_at = models.DateTimeField(_('確認日時'), null=True, blank=True)
    confirmed_by = models.ForeignKey(
        'Staff', verbose_name=_('確認者'),
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='confirmations',
    )
    rejection_reason = models.CharField(_('却下理由'), max_length=200, blank=True, default='')

    is_demo = models.BooleanField(_('デモデータ'), default=False, db_index=True)

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

    def save(self, **kwargs):
        if not self.cancel_token:
            self.cancel_token = self._generate_cancel_token()
        super().save(**kwargs)

    @staticmethod
    def _generate_cancel_token():
        """8文字の英大文字+数字トークンを生成（衝突時はリトライ）。"""
        alphabet = string.ascii_uppercase + string.digits
        for _ in range(10):
            token = ''.join(secrets.choice(alphabet) for _ in range(8))
            if not Schedule.objects.filter(cancel_token=token).exists():
                return token
        raise RuntimeError('cancel_token の一意生成に失敗しました')

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

    def get_store(self):
        """予約店舗を返す（未設定なら主店舗）"""
        return self.store or self.staff.store
