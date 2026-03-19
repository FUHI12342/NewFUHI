#!/usr/bin/env python3
"""
NewFUHI ドキュメント生成スクリプト

Markdown → HTML → PDF 変換（取扱説明書 + テスト報告書）

Usage:
    pip install weasyprint markdown
    python docs/generate_docs.py [manual|test|all]

出力:
    docs/system_manual.html / .pdf   — 取扱説明書
    docs/test_report.html / .pdf     — テスト報告書
"""
import os
import subprocess
import sys
import datetime

# macOS Homebrew: WeasyPrint が libgobject を見つけるために DYLD_LIBRARY_PATH を設定
_brew_prefix = subprocess.run(
    ['brew', '--prefix'], capture_output=True, text=True,
).stdout.strip() if sys.platform == 'darwin' else ''
if _brew_prefix:
    lib_path = os.path.join(_brew_prefix, 'lib')
    os.environ['DYLD_LIBRARY_PATH'] = lib_path + ':' + os.environ.get('DYLD_LIBRARY_PATH', '')

try:
    import markdown
except ImportError:
    print("ERROR: pip install markdown")
    sys.exit(1)


# ───── 共通スタイル ─────

COMMON_CSS = """
@page {
  size: A4;
  margin: 20mm 15mm 25mm 15mm;
  @top-center { content: "HEADER_PLACEHOLDER"; font-size: 9pt; color: #666; }
  @bottom-center { content: "— " counter(page) " —"; font-size: 9pt; color: #666; }
}
* { box-sizing: border-box; }
body {
  font-family: "Hiragino Kaku Gothic ProN","Noto Sans JP","Noto Sans CJK JP",sans-serif;
  font-size: 10pt; line-height: 1.7; color: #222;
  max-width: 100%; margin: 0; padding: 0;
}
h1 {
  font-size: 22pt; color: #1a3a5c;
  border-bottom: 3px solid #1a3a5c;
  padding-bottom: 8px;
  page-break-before: always; margin-top: 0;
}
h1:first-of-type { page-break-before: avoid; }
h2 {
  font-size: 14pt; color: #2c5282;
  border-bottom: 1.5px solid #bee3f8;
  padding-bottom: 4px; margin-top: 24px;
}
h3 { font-size: 11pt; color: #2b6cb0; margin-top: 18px; }
table { width: 100%; border-collapse: collapse; margin: 10px 0 16px 0; font-size: 9pt; }
th, td { border: 1px solid #cbd5e0; padding: 5px 8px; text-align: left; word-break: break-all; }
th { background: #ebf4ff; font-weight: bold; color: #2c5282; }
tr:nth-child(even) { background: #f7fafc; }
code { background: #edf2f7; padding: 1px 4px; border-radius: 3px; font-size: 8.5pt; font-family: "SF Mono","Menlo",monospace; }
pre { background: #1a202c; color: #e2e8f0; padding: 12px; border-radius: 6px; font-size: 8pt; line-height: 1.5; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
pre code { background: none; color: inherit; padding: 0; }
.cover { text-align: center; padding: 120px 0 60px 0; page-break-after: always; }
.cover h1 { font-size: 32pt; border: none; page-break-before: avoid; }
.cover .subtitle { font-size: 14pt; color: #4a5568; margin-top: 16px; }
.cover .date { font-size: 11pt; color: #718096; margin-top: 40px; }
.cover .confidential { font-size: 10pt; color: #a0aec0; margin-top: 60px; }
.toc { page-break-after: always; }
.toc h1 { page-break-before: avoid; }
.toc ol { font-size: 11pt; line-height: 2.2; }
.note { background: #fffbeb; border-left: 4px solid #f6ad55; padding: 10px 14px; margin: 10px 0; font-size: 9pt; }
.info { background: #ebf8ff; border-left: 4px solid #63b3ed; padding: 10px 14px; margin: 10px 0; font-size: 9pt; }
.badge { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 8pt; font-weight: bold; color: #fff; }
.badge-pass { background: #38a169; }
.badge-fail { background: #e53e3e; }
.badge-skip { background: #d69e2e; }
.badge-new { background: #3182ce; }
blockquote { border-left: 4px solid #cbd5e0; margin: 10px 0; padding: 8px 14px; color: #4a5568; background: #f7fafc; }
"""


def md_to_html(md_path, title, header_text, cover_subtitle, confidential_label):
    """Markdown → HTML with cover page"""
    today = datetime.date.today().strftime('%Y年%m月%d日')

    with open(md_path, 'r', encoding='utf-8') as f:
        md_text = f.read()

    body = markdown.markdown(
        md_text,
        extensions=['tables', 'fenced_code', 'toc', 'nl2br'],
    )

    css = COMMON_CSS.replace('HEADER_PLACEHOLDER', header_text)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{css}
</style>
</head>
<body>

<div class="cover">
  <h1>NewFUHI</h1>
  <h1 style="font-size:26pt;">{title}</h1>
  <div class="subtitle">{cover_subtitle}</div>
  <div class="date">Version 1.1 — {today}</div>
  <div class="confidential">{confidential_label}</div>
</div>

{body}

</body>
</html>"""
    return html


def generate_manual():
    """取扱説明書 HTML + PDF 生成"""
    base = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base, 'MANUAL.md')
    html_path = os.path.join(base, 'system_manual.html')
    pdf_path = os.path.join(base, 'system_manual.pdf')

    html = md_to_html(
        md_path,
        title='システム取扱説明書',
        header_text='NewFUHI システム取扱説明書',
        cover_subtitle='予約・店舗・IoT・決済・在庫・給与 統合管理プラットフォーム',
        confidential_label='Confidential — 社内用資料',
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  HTML: {html_path}")

    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(pdf_path)
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"  PDF:  {pdf_path} ({size_kb:.0f} KB)")
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        print("  Install: pip install weasyprint")


def generate_test_report():
    """テスト報告書 HTML + PDF 生成"""
    base = os.path.dirname(os.path.abspath(__file__))
    md_path = os.path.join(base, 'test_results.md')
    html_path = os.path.join(base, 'test_report.html')
    pdf_path = os.path.join(base, 'test_report.pdf')

    html = md_to_html(
        md_path,
        title='テスト報告書',
        header_text='NewFUHI テスト報告書',
        cover_subtitle='自動テスト・カバレッジ・セキュリティレビュー結果',
        confidential_label='Confidential — 社内技術資料',
    )

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  HTML: {html_path}")

    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(pdf_path)
        size_kb = os.path.getsize(pdf_path) / 1024
        print(f"  PDF:  {pdf_path} ({size_kb:.0f} KB)")
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        print("  Install: pip install weasyprint")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'all'

    if target in ('manual', 'all'):
        print("[1/3] 取扱説明書を生成中...")
        generate_manual()

    if target in ('test', 'all'):
        print("[2/3] テスト報告書を生成中...")
        generate_test_report()

    if target in ('spec', 'all'):
        print("[3/3] システム仕様書を生成中...")
        # 既存の generate_system_spec.py を実行
        spec_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'generate_system_spec.py',
        )
        if os.path.exists(spec_script):
            subprocess.run([sys.executable, spec_script], check=True)
        else:
            print("  generate_system_spec.py が見つかりません")

    print("\n完了!")


if __name__ == '__main__':
    main()
