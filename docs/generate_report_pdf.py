#!/usr/bin/env python3
"""SNS自動投稿 調査結果報告書 PDF生成スクリプト"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 日本語フォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))

FONT_MINCHO = 'HeiseiMin-W3'
FONT_GOTHIC = 'HeiseiKakuGo-W5'

# カラー
PRIMARY = HexColor('#1DA1F2')  # Twitter blue
DARK = HexColor('#14171A')
GRAY = HexColor('#657786')
LIGHT_BG = HexColor('#F5F8FA')
GREEN = HexColor('#17BF63')
RED = HexColor('#E0245E')
YELLOW = HexColor('#FFAD1F')
WHITE = HexColor('#FFFFFF')

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), 'report_sns_auto_posting.pdf')


def build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'JTitle', fontName=FONT_GOTHIC, fontSize=20, leading=28,
        textColor=DARK, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'JSubtitle', fontName=FONT_GOTHIC, fontSize=11, leading=16,
        textColor=GRAY, spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        'JH1', fontName=FONT_GOTHIC, fontSize=15, leading=22,
        textColor=PRIMARY, spaceBefore=16, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        'JH2', fontName=FONT_GOTHIC, fontSize=12, leading=18,
        textColor=DARK, spaceBefore=12, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        'JBody', fontName=FONT_MINCHO, fontSize=10, leading=16,
        textColor=DARK, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'JBodyBold', fontName=FONT_GOTHIC, fontSize=10, leading=16,
        textColor=DARK, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'JBullet', fontName=FONT_MINCHO, fontSize=10, leading=16,
        textColor=DARK, leftIndent=16, spaceAfter=2,
        bulletIndent=4, bulletFontName=FONT_GOTHIC,
    ))
    styles.add(ParagraphStyle(
        'JSmall', fontName=FONT_MINCHO, fontSize=8, leading=12,
        textColor=GRAY, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        'JConclusion', fontName=FONT_GOTHIC, fontSize=11, leading=18,
        textColor=WHITE, backColor=PRIMARY, spaceAfter=8,
        leftIndent=8, rightIndent=8, spaceBefore=4,
        borderPadding=(6, 8, 6, 8),
    ))
    return styles


def make_table(data, col_widths=None, header=True):
    """共通テーブルスタイル"""
    style_cmds = [
        ('FONT', (0, 0), (-1, -1), FONT_MINCHO, 9),
        ('FONT', (0, 0), (-1, 0), FONT_GOTHIC, 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), DARK),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    if header:
        style_cmds += [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ]
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(style_cmds))
    return t


def build_report():
    s = build_styles()
    elements = []

    # === 表紙 ===
    elements.append(Spacer(1, 60))
    elements.append(Paragraph('SNS自動投稿機能', s['JTitle']))
    elements.append(Paragraph('調査結果報告書', s['JTitle']))
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width='100%', thickness=2, color=PRIMARY))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph('Timebaibai (占いサロンチャンス)', s['JSubtitle']))
    elements.append(Paragraph('作成日: 2026年3月28日', s['JSubtitle']))
    elements.append(Spacer(1, 40))

    # エグゼクティブサマリー
    elements.append(Paragraph('エグゼクティブサマリー', s['JH1']))
    elements.append(Paragraph(
        'Timebaibaiで作成したシフト・スタッフ情報をX (Twitter) に自動投稿し、'
        '集客と業務効率化を実現する機能の技術調査を実施しました。'
        '結論として、<b>X APIによる自動投稿は規約上OK・技術的に実現可能</b>です。'
        '一方、Google Business Profile APIは不安定なため除外が正解です。',
        s['JBody'],
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '競合調査の結果、サロンボード（リクルート）を含む主要予約システムに'
        'SNS自動投稿機能はなく、<b>Timebaibaiの差別化ポイント</b>になります。',
        s['JBody'],
    ))

    # === 1. X API ===
    elements.append(PageBreak())
    elements.append(Paragraph('1. X (Twitter) API v2 Free tier', s['JH1']))

    elements.append(Paragraph('結論: 自動投稿は規約上OK。致命的なレート制限あり。', s['JConclusion']))

    elements.append(Paragraph('1.1 レート制限', s['JH2']))
    elements.append(make_table([
        ['項目', '値', '備考'],
        ['POST /2/tweets (アプリ全体)', '17リクエスト/24時間', '全店舗合計で共有！'],
        ['月間投稿上限', '500投稿/月', 'enrollment day基準'],
        ['GET /2/tweets', '100リクエスト/月', 'ほぼ使えない'],
        ['料金', '$0/月', 'Free tier'],
        ['Pay-per-use代替', '~$0.01/投稿', '$5/月で500投稿'],
    ], col_widths=[55*mm, 45*mm, 65*mm]))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph('1.2 トークンライフサイクル', s['JH2']))
    elements.append(make_table([
        ['項目', '値'],
        ['Access token有効期限', '2時間 (7200秒)'],
        ['Refresh token有効期限', '6ヶ月 (ワンタイム使用)'],
        ['認証方式', 'OAuth 2.0 PKCE (Confidential Client)'],
        ['スコープ', 'tweet.read tweet.write users.read offline.access'],
    ], col_widths=[55*mm, 110*mm]))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph('1.3 重要な注意点', s['JH2']))
    elements.append(Paragraph('- 17件/日制限はアプリ全体で共有（全店舗合計）', s['JBullet']))
    elements.append(Paragraph('- 失敗リクエスト (429/503/timeout) もカウント消費', s['JBullet']))
    elements.append(Paragraph('- Refresh tokenはワンタイム → 複数ワーカーの同時リフレッシュで全無効化リスク', s['JBullet']))
    elements.append(Paragraph('- 月間リセットはenrollment day基準（カレンダー月ではない）', s['JBullet']))
    elements.append(Paragraph('- 日本語は加重カウント（1文字=2）→ 実質140文字相当', s['JBullet']))

    # === 2. GBP ===
    elements.append(Paragraph('2. Google Business Profile API', s['JH1']))
    elements.append(Paragraph('結論: 新規実装は非推奨。除外が正解。', s['JConclusion']))

    elements.append(Paragraph('- レガシーAPI v4 (mybusiness.googleapis.com) がまだ公式ドキュメントに記載', s['JBullet']))
    elements.append(Paragraph('- しかし広範囲で403エラーが報告されている (2024〜2025年)', s['JBullet']))
    elements.append(Paragraph('- 後継APIは存在しない', s['JBullet']))
    elements.append(Paragraph('- API審査に3〜4週間かかる', s['JBullet']))
    elements.append(Paragraph('- 代替案: サードパーティ経由 (Ayrshare等) → 月$29〜$99', s['JBullet']))

    # === 3. 競合分析 ===
    elements.append(Paragraph('3. 競合分析', s['JH1']))

    elements.append(Paragraph('3.1 サロンボード (Recruit)', s['JH2']))
    elements.append(Paragraph(
        '日本最大の美容・サロン予約システム。SNS自動投稿機能は持っていない。'
        'X/Instagram連携は手動リンク共有のみ。',
        s['JBody'],
    ))

    elements.append(Paragraph('3.2 主要競合比較', s['JH2']))
    elements.append(make_table([
        ['システム', 'SNS自動投稿', 'SNS連携方法'],
        ['サロンボード (Recruit)', 'なし', '手動リンク共有'],
        ['STORES予約', 'なし', '予約ページURL共有'],
        ['Airリザーブ', 'なし', 'なし'],
        ['Timebaibai (本システム)', '実装済み', 'X API自動投稿'],
    ], col_widths=[55*mm, 40*mm, 70*mm]))

    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        '→ SNS自動投稿はTimebaibai独自の差別化機能。'
        '店舗オーナーがシフトを公開するだけで自動的にXに投稿される。',
        s['JBodyBold'],
    ))

    # === 4. アーキテクチャ ===
    elements.append(PageBreak())
    elements.append(Paragraph('4. 技術アーキテクチャ', s['JH1']))

    elements.append(Paragraph('4.1 採用したベストプラクティス', s['JH2']))
    elements.append(make_table([
        ['パターン', '目的', '実装方法'],
        ['transaction.on_commit()', 'Celeryタスクの安全なdispatch', 'シフト公開トリガーで使用'],
        ['専用キュー + 単一ワーカー', 'グローバルレート制限遵守', 'x_api キュー, concurrency=1'],
        ['Redis Sorted Set', 'スライディングウィンドウ制限', '24h日次制限管理'],
        ['Redis分散ロック (NX+EX)', 'トークンリフレッシュ排他制御', '複数ワーカー同時更新防止'],
        ['EncryptedCharField', 'トークン暗号化保存', '既存Fernet暗号化を再利用'],
        ['冪等性チェック', '重複投稿防止', 'PostHistory.external_post_id'],
    ], col_widths=[50*mm, 50*mm, 65*mm]))

    elements.append(Paragraph('4.2 レート制限アーキテクチャ', s['JH2']))
    elements.append(make_table([
        ['制限タイプ', 'Redis Key', '閾値', 'TTL'],
        ['月間 (アプリ)', 'x_api:app_posts:{month}', '480 (安全マージン20)', '35日'],
        ['月間 (店舗別)', 'x_api:store_posts:{id}:{month}', '50/店舗', '35日'],
        ['日次 (アプリ)', 'x_api:daily_posts (Sorted Set)', '16 (バッファ1)', '25時間'],
        ['トークンロック', 'x_api:token_refresh:{id}', '-', '60秒'],
    ], col_widths=[35*mm, 55*mm, 40*mm, 30*mm]))

    # === 5. コスト ===
    elements.append(Paragraph('5. コスト見積もり', s['JH1']))
    elements.append(make_table([
        ['項目', '月額コスト', '備考'],
        ['X API Free tier', '$0', '17件/日, 500件/月'],
        ['Redis (既存流用)', '$0', 'Celery brokerと共用'],
        ['新規pip依存', '$0', 'requests, redis等は既存'],
        ['合計', '$0/月', ''],
    ], col_widths=[55*mm, 40*mm, 70*mm]))

    elements.append(Spacer(1, 12))
    elements.append(Paragraph('将来のスケーリング選択肢:', s['JH2']))
    elements.append(Paragraph('- Basic tier ($200/月): 制限大幅緩和、10,000ツイート/月', s['JBullet']))
    elements.append(Paragraph('- Pay-per-use: ~$5/月 (500投稿、$0.01/投稿)', s['JBullet']))

    # === 6. 実装状況 ===
    elements.append(Paragraph('6. 実装状況', s['JH1']))
    elements.append(make_table([
        ['カテゴリ', 'ファイル', 'テスト数'],
        ['モデル (3モデル)', 'booking/models/social_posting.py', '9'],
        ['コンテンツ生成', 'booking/services/post_generator.py', '17'],
        ['X API投稿', 'booking/services/x_posting_service.py', '10'],
        ['レート制限', 'booking/services/x_rate_limiter.py', '-'],
        ['ディスパッチ', 'booking/services/post_dispatcher.py', '11'],
        ['OAuth認証', 'booking/views_social_oauth.py', '-'],
        ['Django Admin', 'booking/admin/social_posting.py', '-'],
        ['Celeryタスク', 'booking/tasks.py (+70行)', '9'],
        ['合計', '8新規 + 9変更ファイル', '61テスト (全通過)'],
    ], col_widths=[40*mm, 75*mm, 25*mm]))

    # === 7. 次のステップ ===
    elements.append(Spacer(1, 12))
    elements.append(Paragraph('7. 次のステップ', s['JH1']))
    elements.append(Paragraph('1. X Developer Portalでアプリ作成 → OAuth認証情報取得', s['JBullet']))
    elements.append(Paragraph('2. .envにX_CLIENT_ID, X_CLIENT_SECRET, X_REDIRECT_URIを設定', s['JBullet']))
    elements.append(Paragraph('3. Django Admin → 「X連携」ボタンでOAuth認証', s['JBullet']))
    elements.append(Paragraph('4. PostTemplateでテンプレート作成', s['JBullet']))
    elements.append(Paragraph('5. 手動投稿テスト → シフト公開自動投稿テスト', s['JBullet']))
    elements.append(Paragraph('6. 本番デプロイ: x_api専用Celeryワーカー起動', s['JBullet']))

    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width='100%', thickness=1, color=GRAY))
    elements.append(Paragraph('以上', s['JSmall']))

    return elements


def main():
    doc = SimpleDocTemplate(
        OUTPUT_PATH,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    elements = build_report()
    doc.build(elements)
    print(f'PDF generated: {OUTPUT_PATH}')


if __name__ == '__main__':
    main()
