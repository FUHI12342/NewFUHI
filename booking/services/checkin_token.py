"""HMAC-signed QR tokens and backup codes for reservation checkin."""
import hashlib
import hmac
import io
import secrets
from datetime import datetime, timedelta

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone


def _get_secret() -> str:
    """Return CHECKIN_QR_SECRET, falling back to SECRET_KEY."""
    secret = getattr(settings, 'CHECKIN_QR_SECRET', '') or ''
    if not secret:
        secret = settings.SECRET_KEY
    return secret


def make_qr_token(reservation_number: str, appointment_end: datetime) -> str:
    """Generate a signed QR token: {res_num}|{expires_unix}|{hmac_hex}."""
    expires_unix = str(int(appointment_end.timestamp()))
    message = f"{reservation_number}|{expires_unix}"
    sig = hmac.new(
        _get_secret().encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return f"{reservation_number}|{expires_unix}|{sig}"


def verify_qr_token(token: str) -> tuple[bool, str, str]:
    """Verify a signed QR token.

    Returns (valid, reservation_number, error_message).
    """
    parts = token.split('|')
    if len(parts) != 3:
        return (False, '', '不正なQRコード形式です')

    reservation_number, expires_unix, provided_sig = parts

    # Verify signature
    message = f"{reservation_number}|{expires_unix}"
    expected_sig = hmac.new(
        _get_secret().encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(provided_sig, expected_sig):
        return (False, '', 'QRコードの署名が無効です')

    # Check expiration
    try:
        expires_dt = datetime.fromtimestamp(int(expires_unix), tz=timezone.utc)
    except (ValueError, OSError):
        return (False, '', 'QRコードの有効期限が不正です')

    if timezone.now() > expires_dt:
        return (False, reservation_number, 'QRコードの有効期限が切れています')

    return (True, reservation_number, '')


def generate_backup_code(store, date) -> str:
    """Generate a unique 6-digit backup code within store x date scope."""
    from booking.models import Schedule

    for _ in range(10):
        code = f"{secrets.randbelow(1_000_000):06d}"
        exists = Schedule.objects.filter(
            staff__store=store,
            start__date=date,
            checkin_backup_code=code,
            is_checked_in=False,
            is_cancelled=False,
        ).exists()
        if not exists:
            return code
    raise RuntimeError('Failed to generate unique backup code')


def is_within_checkin_window(schedule) -> bool:
    """Check if now is within 30 min before start to end of appointment."""
    now = timezone.now()
    window_start = schedule.start - timedelta(minutes=30)
    return window_start <= now <= schedule.end


def generate_signed_checkin_qr(
    reservation_number: str,
    appointment_end: datetime,
) -> ContentFile:
    """Generate a QR code image containing the signed token."""
    token = make_qr_token(reservation_number, appointment_end)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f'qr_{reservation_number}.png')
