"""電子透かし（Digital Watermark）テンプレートタグ

4層の透かしでコンテンツの無断コピーを追跡可能にする:
1. <meta> タグにライセンスハッシュ（検索エンジン/法的証拠）
2. ゼロ幅文字ステガノグラフィ（目視不可能、コピペ追跡）
3. HTMLコメントにハッシュID（ソース閲覧で検出）
4. CSS クラス名パターン（テンプレート盗用検出）
"""
import hashlib
import hmac
import struct
import time

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

# ゼロ幅文字マッピング
_ZW_ZERO = '\u200b'       # Zero-Width Space = bit 0
_ZW_ONE = '\u200c'        # Zero-Width Non-Joiner = bit 1
_ZW_SEP = '\u200d'        # Zero-Width Joiner = byte separator
_ZW_MARKER = '\ufeff'     # BOM = start/end marker

# サイト識別子
_SITE_ID = 'timebaibai.com'


def encode_to_zwc(data: bytes) -> str:
    """バイト列をゼロ幅文字列にエンコードする。"""
    chars = [_ZW_MARKER]
    for byte_val in data:
        for i in range(7, -1, -1):
            chars.append(_ZW_ONE if (byte_val >> i) & 1 else _ZW_ZERO)
        chars.append(_ZW_SEP)
    chars.append(_ZW_MARKER)
    return ''.join(chars)


def decode_from_zwc(text: str) -> bytes:
    """テキストからゼロ幅文字を抽出しバイト列にデコードする。"""
    # ゼロ幅文字のみ抽出
    zwc_chars = [c for c in text if c in (_ZW_ZERO, _ZW_ONE, _ZW_SEP, _ZW_MARKER)]
    zwc_str = ''.join(zwc_chars)

    start = zwc_str.find(_ZW_MARKER)
    end = zwc_str.rfind(_ZW_MARKER)
    if start == -1 or end == -1 or start == end:
        return b''

    content = zwc_str[start + 1:end]
    result = bytearray()
    byte_val = 0
    bit_count = 0

    for ch in content:
        if ch == _ZW_SEP:
            if bit_count == 8:
                result.append(byte_val)
            byte_val = 0
            bit_count = 0
            continue
        if ch == _ZW_ZERO:
            byte_val = (byte_val << 1)
            bit_count += 1
        elif ch == _ZW_ONE:
            byte_val = (byte_val << 1) | 1
            bit_count += 1

    return bytes(result)


def _get_secret() -> str:
    return getattr(settings, 'SECRET_KEY', 'fallback-watermark-key')


def generate_fingerprint() -> bytes:
    """サイト固有フィンガープリントを生成する。

    構造: site_id(可変) + timestamp_hour(4B) + hmac_sig(8B)
    """
    timestamp_hour = int(time.time()) // 3600
    payload = _SITE_ID.encode() + struct.pack('>I', timestamp_hour)
    sig = hmac.new(
        _get_secret().encode(),
        payload,
        hashlib.sha256,
    ).digest()[:8]
    return payload + sig


def verify_fingerprint(data: bytes) -> dict:
    """フィンガープリントを検証する。

    Returns:
        dict with keys: valid, site_id, timestamp_hour, error
    """
    site_id_bytes = _SITE_ID.encode()
    site_len = len(site_id_bytes)

    # 最低長: site_id + 4B timestamp + 8B sig
    if len(data) < site_len + 12:
        return {'valid': False, 'error': 'データが短すぎます'}

    extracted_site = data[:site_len]
    if extracted_site != site_id_bytes:
        return {
            'valid': False,
            'site_id': extracted_site.decode(errors='replace'),
            'error': 'サイトIDが一致しません',
        }

    timestamp_hour = struct.unpack('>I', data[site_len:site_len + 4])[0]
    extracted_sig = data[site_len + 4:site_len + 12]

    # 署名再計算
    payload = data[:site_len + 4]
    expected_sig = hmac.new(
        _get_secret().encode(),
        payload,
        hashlib.sha256,
    ).digest()[:8]

    valid = hmac.compare_digest(extracted_sig, expected_sig)
    return {
        'valid': valid,
        'site_id': _SITE_ID,
        'timestamp_hour': timestamp_hour,
        'error': None if valid else '署名が一致しません（SECRET_KEYが異なる可能性）',
    }


def _license_hash() -> str:
    """ライセンスハッシュ（16文字）を生成する。"""
    return hashlib.sha256(
        f"{_SITE_ID}:{_get_secret()[:8]}".encode()
    ).hexdigest()[:16]


@register.simple_tag
def watermark():
    """<head> 内に4層の電子透かしを埋め込む。

    使用法: {% load watermark %}{% watermark %}
    """
    license_h = _license_hash()
    fingerprint = generate_fingerprint()
    zwc = encode_to_zwc(fingerprint)

    # CSS クラス名にサイトハッシュを符号化（テンプレート盗用検出用）
    css_marker = f"tb{license_h[:8]}"

    html_parts = [
        # Layer 1: Meta tags
        f'<meta name="content-license" content="proprietary:{license_h}">',
        '<meta name="generator" content="NewFUHI CMS">',
        # Layer 2: Zero-width char fingerprint (invisible)
        f'<span aria-hidden="true" class="{css_marker}" '
        f'style="position:absolute;width:0;height:0;overflow:hidden;pointer-events:none">'
        f'{zwc}</span>',
        # Layer 3: HTML comment hash
        f'<!-- TBWM:{license_h} -->',
    ]
    return mark_safe('\n'.join(html_parts))


@register.simple_tag
def watermark_verify_info():
    """検証用情報を返す（管理画面デバッグ用）。"""
    return {
        'license_hash': _license_hash(),
        'site_id': _SITE_ID,
        'zwc_sample_length': len(encode_to_zwc(generate_fingerprint())),
    }
