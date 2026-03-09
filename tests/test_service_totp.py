"""TOTPサービステスト"""
import pytest
import time as time_mod


class TestTOTPService:
    def test_generate_secret(self):
        from booking.services.totp_service import generate_totp_secret
        secret = generate_totp_secret()
        assert len(secret) > 10

    def test_get_current_totp(self):
        from booking.services.totp_service import generate_totp_secret, get_current_totp
        secret = generate_totp_secret()
        code = get_current_totp(secret)
        assert len(code) == 6
        assert code.isdigit()

    def test_verify_valid_totp(self):
        from booking.services.totp_service import generate_totp_secret, get_current_totp, verify_totp
        secret = generate_totp_secret()
        code = get_current_totp(secret)
        assert verify_totp(secret, code)

    def test_verify_invalid_totp(self):
        from booking.services.totp_service import generate_totp_secret, verify_totp
        secret = generate_totp_secret()
        assert not verify_totp(secret, '000000')

    def test_qr_payload_roundtrip(self):
        from booking.services.totp_service import (
            generate_totp_secret, get_current_totp,
            generate_qr_payload, verify_qr_payload,
        )
        secret = generate_totp_secret()
        code = get_current_totp(secret)
        payload = generate_qr_payload(42, code, secret)
        is_valid, staff_id, error = verify_qr_payload(payload, secret)
        assert is_valid
        assert staff_id == 42
        assert error == ''
