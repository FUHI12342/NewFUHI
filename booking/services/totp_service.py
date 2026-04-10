"""TOTP勤怠サービス - QRコード打刻用のTOTP生成・検証"""
import hashlib
import hmac
import time
import logging

logger = logging.getLogger(__name__)


def generate_totp_secret():
    """新しいTOTPシークレットを生成する"""
    try:
        import pyotp
        return pyotp.random_base32()
    except ImportError:
        import secrets
        return secrets.token_hex(20)


def get_current_totp(secret, interval=30):
    """現在のTOTPコードを取得する"""
    try:
        import pyotp
        totp = pyotp.TOTP(secret, interval=interval)
        return totp.now()
    except ImportError:
        # Fallback: simple time-based numeric code
        t = int(time.time() // interval)
        h = hashlib.sha256(f"{secret}{t}".encode()).digest()
        code = int.from_bytes(h[:4], 'big') % 1000000
        return f"{code:06d}"


def verify_totp(secret, code, interval=30, valid_window=1):
    """TOTPコードを検証する"""
    try:
        import pyotp
        totp = pyotp.TOTP(secret, interval=interval)
        return totp.verify(code, valid_window=valid_window)
    except ImportError:
        # Fallback verification
        current = get_current_totp(secret, interval)
        return code == current


def generate_qr_payload(staff_id, totp_code, secret):
    """QR打刻用ペイロードを生成する

    Format: {staff_id}:{totp_code}:{timestamp}:{hmac_signature}
    """
    timestamp = str(int(time.time()))
    message = f"{staff_id}{totp_code}{timestamp}"
    signature = hmac.new(
        secret.encode('utf-8'),
        message.encode('utf-8'),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"{staff_id}:{totp_code}:{timestamp}:{signature}"


def verify_qr_payload(payload, secret, max_age_seconds=60):
    """QRペイロードを検証する

    Returns:
        tuple: (is_valid, staff_id, error_message)
    """
    try:
        parts = payload.split(':')
        if len(parts) != 4:
            return False, None, 'Invalid payload format'

        staff_id_str, totp_code, timestamp_str, signature = parts
        staff_id = int(staff_id_str)
        timestamp = int(timestamp_str)

        # タイムスタンプ検証
        now = int(time.time())
        if abs(now - timestamp) > max_age_seconds:
            return False, staff_id, 'QR code expired'

        # HMAC検証
        message = f"{staff_id}{totp_code}{timestamp_str}"
        expected_full = hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Accept both full-length (new) and truncated (legacy) signatures
        if len(signature) == 16:
            expected = expected_full[:16]
        else:
            expected = expected_full

        if not hmac.compare_digest(signature, expected):
            return False, staff_id, 'Invalid signature'

        # TOTP検証
        if not verify_totp(secret, totp_code):
            return False, staff_id, 'Invalid TOTP code'

        return True, staff_id, ''
    except (ValueError, IndexError) as e:
        return False, None, f'Payload parse error: {e}'


def check_duplicate_stamp(staff_id, stamp_type, minutes=5):
    """重複打刻チェック（指定分数以内の同一種別打刻を拒否）"""
    from django.utils import timezone
    from datetime import timedelta
    from booking.models import AttendanceStamp

    cutoff = timezone.now() - timedelta(minutes=minutes)
    return AttendanceStamp.objects.filter(
        staff_id=staff_id,
        stamp_type=stamp_type,
        stamped_at__gte=cutoff,
        is_valid=True,
    ).exists()


def check_geo_fence(config_lat, config_lng, user_lat, user_lng, radius_m):
    """ジオフェンスチェック（haversine距離計算）"""
    import math

    R = 6371000  # Earth radius in meters
    lat1 = math.radians(config_lat)
    lat2 = math.radians(user_lat)
    dlat = math.radians(user_lat - config_lat)
    dlng = math.radians(user_lng - config_lng)

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c

    return distance <= radius_m
