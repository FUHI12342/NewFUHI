"""電子透かしテンプレートタグのテスト"""
import pytest

from booking.templatetags.watermark import (
    decode_from_zwc,
    encode_to_zwc,
    generate_fingerprint,
    verify_fingerprint,
)


class TestZWCEncoding:
    """ゼロ幅文字エンコード/デコードのテスト"""

    def test_roundtrip(self):
        """エンコード→デコードで元データが復元される。"""
        data = b'hello world'
        encoded = encode_to_zwc(data)
        decoded = decode_from_zwc(encoded)
        assert decoded == data

    def test_roundtrip_binary(self):
        """バイナリデータもラウンドトリップ可能。"""
        data = bytes(range(256))
        encoded = encode_to_zwc(data)
        decoded = decode_from_zwc(encoded)
        assert decoded == data

    def test_decode_from_mixed_text(self):
        """通常テキストに埋め込まれたZWCからデコードできる。"""
        data = b'test'
        encoded = encode_to_zwc(data)
        mixed = f'<div>普通のHTML{encoded}ここも普通</div>'
        decoded = decode_from_zwc(mixed)
        assert decoded == data

    def test_decode_empty_string(self):
        """空文字列からはデコードできない。"""
        assert decode_from_zwc('') == b''

    def test_decode_no_markers(self):
        """マーカーなしのテキストからはデコードできない。"""
        assert decode_from_zwc('普通のテキスト') == b''

    def test_encoded_invisible(self):
        """エンコード結果は表示幅ゼロの文字のみ。"""
        data = b'test'
        encoded = encode_to_zwc(data)
        visible = [c for c in encoded if c.isprintable() and not c.isspace()
                   and ord(c) > 0x20 and c not in '\u200b\u200c\u200d\ufeff']
        assert visible == []


class TestFingerprint:
    """フィンガープリント生成・検証のテスト"""

    def test_generate_and_verify(self):
        """生成したフィンガープリントが検証に通る。"""
        fp = generate_fingerprint()
        result = verify_fingerprint(fp)
        assert result['valid'] is True
        assert result['site_id'] == 'timebaibai.com'
        assert result['error'] is None

    def test_tampered_data_fails(self):
        """改ざんデータは検証に失敗する。"""
        fp = bytearray(generate_fingerprint())
        fp[-1] ^= 0xFF  # 最後のバイトを反転
        result = verify_fingerprint(bytes(fp))
        assert result['valid'] is False

    def test_short_data_fails(self):
        """短すぎるデータはエラーになる。"""
        result = verify_fingerprint(b'short')
        assert result['valid'] is False
        assert 'データが短すぎます' in result['error']

    def test_wrong_site_id_fails(self):
        """異なるサイトIDは検証に失敗する。"""
        wrong = b'wrongsite.com' + b'\x00' * 12
        result = verify_fingerprint(wrong)
        assert result['valid'] is False


class TestFullPipeline:
    """エンコード→埋め込み→抽出→検証の統合テスト"""

    def test_full_watermark_pipeline(self):
        """フィンガープリント生成→ZWCエンコード→デコード→検証の全フロー。"""
        fp = generate_fingerprint()
        encoded = encode_to_zwc(fp)

        # HTMLに埋め込み
        html = f'<html><body><span>{encoded}</span><p>Content</p></body></html>'

        # 抽出・検証
        decoded = decode_from_zwc(html)
        result = verify_fingerprint(decoded)
        assert result['valid'] is True
        assert result['site_id'] == 'timebaibai.com'
