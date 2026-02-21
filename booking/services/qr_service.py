import qrcode
import io
from django.core.files.base import ContentFile


def generate_checkin_qr(reservation_number: str) -> ContentFile:
    """Generate a QR code image for the given reservation number."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(reservation_number)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return ContentFile(buffer.read(), name=f'qr_{reservation_number}.png')
