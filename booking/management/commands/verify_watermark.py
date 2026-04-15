"""電子透かし検証コマンド

HTMLファイルまたはURLからゼロ幅文字フィンガープリントを抽出・検証する。

Usage:
    python manage.py verify_watermark path/to/file.html
    python manage.py verify_watermark --url https://example.com/page
    python manage.py verify_watermark --text "コピペされたテキスト"
"""
import sys

from django.core.management.base import BaseCommand

from booking.templatetags.watermark import (
    decode_from_zwc,
    verify_fingerprint,
    _license_hash,
)


class Command(BaseCommand):
    help = '電子透かしの検証: HTMLファイル/URL/テキストからフィンガープリントを抽出'

    def add_arguments(self, parser):
        parser.add_argument(
            'file',
            nargs='?',
            help='検証対象のHTMLファイルパス',
        )
        parser.add_argument(
            '--url',
            help='検証対象のURL（HTMLを取得して検証）',
        )
        parser.add_argument(
            '--text',
            help='検証対象のテキスト（コピペ内容を直接渡す）',
        )
        parser.add_argument(
            '--show-hash',
            action='store_true',
            help='現在のサイトのライセンスハッシュを表示',
        )

    def handle(self, *args, **options):
        if options['show_hash']:
            self.stdout.write(f"ライセンスハッシュ: {_license_hash()}")
            self.stdout.write(f"サイトID: timebaibai.com")
            return

        content = self._get_content(options)
        if not content:
            self.stderr.write(self.style.ERROR(
                'ファイルパス、--url、または --text を指定してください'
            ))
            sys.exit(1)

        # ゼロ幅文字を抽出
        data = decode_from_zwc(content)
        if not data:
            self.stderr.write(self.style.WARNING(
                '電子透かしが検出されませんでした（ゼロ幅文字なし）'
            ))
            # フォールバック: HTMLコメントからハッシュを探す
            self._check_comment_hash(content)
            self._check_meta_license(content)
            return

        self.stdout.write(self.style.SUCCESS('電子透かしを検出しました'))
        self.stdout.write(f"  デコードデータ: {data.hex()}")
        self.stdout.write(f"  データ長: {len(data)} bytes")

        # 検証
        result = verify_fingerprint(data)
        if result['valid']:
            self.stdout.write(self.style.SUCCESS('  検証結果: 有効（このサイトのコンテンツです）'))
            self.stdout.write(f"  サイトID: {result['site_id']}")
            self.stdout.write(f"  タイムスタンプ（時間単位）: {result['timestamp_hour']}")
        else:
            self.stdout.write(self.style.WARNING(f"  検証結果: 無効 — {result['error']}"))
            if result.get('site_id'):
                self.stdout.write(f"  検出サイトID: {result['site_id']}")

        # 追加チェック
        self._check_comment_hash(content)
        self._check_meta_license(content)

    def _get_content(self, options):
        if options.get('text'):
            return options['text']

        if options.get('url'):
            try:
                import urllib.request
                with urllib.request.urlopen(options['url'], timeout=10) as resp:
                    return resp.read().decode('utf-8', errors='replace')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'URL取得エラー: {e}'))
                return None

        if options.get('file'):
            try:
                with open(options['file'], 'r', encoding='utf-8') as f:
                    return f.read()
            except FileNotFoundError:
                self.stderr.write(self.style.ERROR(
                    f"ファイルが見つかりません: {options['file']}"
                ))
                return None

        return None

    def _check_comment_hash(self, content):
        """HTMLコメント内のハッシュを検索する。"""
        import re
        matches = re.findall(r'<!-- TBWM:([a-f0-9]+) -->', content)
        if matches:
            expected = _license_hash()
            for h in matches:
                if h == expected:
                    self.stdout.write(self.style.SUCCESS(
                        f'  HTMLコメント透かし: 一致 (TBWM:{h})'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'  HTMLコメント透かし: 不一致 (TBWM:{h}, 期待値:{expected})'
                    ))

    def _check_meta_license(self, content):
        """<meta name="content-license"> タグを検索する。"""
        import re
        matches = re.findall(
            r'<meta\s+name="content-license"\s+content="([^"]+)"',
            content,
        )
        if matches:
            for val in matches:
                self.stdout.write(f'  メタタグライセンス: {val}')
