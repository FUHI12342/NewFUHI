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


def generate_table_qr(table_url: str, table_label: str) -> ContentFile:
    """Generate a QR code image for table ordering URL with seat name label."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(table_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

    # Add seat name label below the QR code
    from PIL import Image, ImageDraw, ImageFont
    qr_w, qr_h = qr_img.size
    label_height = 40
    canvas = Image.new('RGB', (qr_w, qr_h + label_height), 'white')
    canvas.paste(qr_img, (0, 0))

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 20)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
        except (OSError, IOError):
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), table_label, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (qr_w - text_w) // 2
    text_y = qr_h + (label_height - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), table_label, fill='black', font=font)

    buffer = io.BytesIO()
    canvas.save(buffer, format='PNG')
    buffer.seek(0)
    safe_label = table_label.replace('/', '_').replace(' ', '_')
    return ContentFile(buffer.read(), name=f'table_qr_{safe_label}.png')
