"""Tests for QR code generation service."""
import pytest

try:
    import qrcode  # noqa: F401
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

pytestmark = pytest.mark.skipif(not HAS_QRCODE, reason='qrcode package not installed')


from django.core.files.base import ContentFile


class TestGenerateCheckinQR:
    """Tests for generate_checkin_qr."""

    def test_returns_content_file(self):
        """generate_checkin_qr returns a ContentFile."""
        from booking.services.qr_service import generate_checkin_qr
        result = generate_checkin_qr('RES-12345')
        assert isinstance(result, ContentFile)

    def test_file_name_contains_reservation_number(self):
        """Result file name contains the reservation number."""
        from booking.services.qr_service import generate_checkin_qr
        result = generate_checkin_qr('RES-67890')
        assert 'RES-67890' in result.name

    def test_file_is_png(self):
        """Result file is a PNG image."""
        from booking.services.qr_service import generate_checkin_qr
        result = generate_checkin_qr('RES-PNG-CHECK')
        assert result.name.endswith('.png')


class TestGenerateTableQR:
    """Tests for generate_table_qr."""

    def test_returns_content_file(self):
        """generate_table_qr returns a ContentFile."""
        from booking.services.qr_service import generate_table_qr
        result = generate_table_qr('https://example.com/t/abc/', 'Table A1')
        assert isinstance(result, ContentFile)

    def test_sanitizes_label_slash(self):
        """generate_table_qr replaces / with _ in file name."""
        from booking.services.qr_service import generate_table_qr
        result = generate_table_qr('https://example.com/t/abc/', 'Floor1/A1')
        assert '/' not in result.name.replace('table_qr_', '')

    def test_sanitizes_label_space(self):
        """generate_table_qr replaces spaces with _ in file name."""
        from booking.services.qr_service import generate_table_qr
        result = generate_table_qr('https://example.com/t/abc/', 'Table A1')
        label_part = result.name.replace('table_qr_', '').replace('.png', '')
        assert ' ' not in label_part
