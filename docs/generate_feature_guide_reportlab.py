#!/usr/bin/env python3
"""Timebaibai 新機能ガイド PDF — ReportLab CIDフォント版（日本語対応）"""
import datetime
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)

# CIDフォント登録（フォントファイル不要）
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))

BLUE = colors.HexColor('#1e40af')
LIGHT_BLUE = colors.HexColor('#3b82f6')
DARK = colors.HexColor('#1a1a1a')
GRAY = colors.HexColor('#6b7280')
BG_BLUE = colors.HexColor('#eff6ff')
BG_GREEN = colors.HexColor('#ecfdf5')
BG_YELLOW = colors.HexColor('#fef3c7')
WHITE = colors.white

styles = getSampleStyleSheet()

# 日本語スタイル定義
S_TITLE = ParagraphStyle('JTitle', fontName='HeiseiKakuGo-W5', fontSize=28,
                         textColor=BLUE, alignment=TA_CENTER, leading=36,
                         spaceAfter=6)
S_SUBTITLE = ParagraphStyle('JSub', fontName='HeiseiKakuGo-W5', fontSize=16,
                            textColor=GRAY, alignment=TA_CENTER, leading=22,
                            spaceAfter=4)
S_H1 = ParagraphStyle('JH1', fontName='HeiseiKakuGo-W5', fontSize=18,
                       textColor=BLUE, leading=24, spaceAfter=8, spaceBefore=12)
S_H2 = ParagraphStyle('JH2', fontName='HeiseiKakuGo-W5', fontSize=13,
                       textColor=colors.HexColor('#1e3a5f'), leading=18,
                       spaceAfter=6, spaceBefore=10)
S_H3 = ParagraphStyle('JH3', fontName='HeiseiKakuGo-W5', fontSize=11,
                       textColor=DARK, leading=15, spaceAfter=4, spaceBefore=8)
S_BODY = ParagraphStyle('JBody', fontName='HeiseiKakuGo-W5', fontSize=9.5,
                        textColor=DARK, leading=15, spaceAfter=4,
                        wordWrap='CJK')
S_SMALL = ParagraphStyle('JSmall', fontName='HeiseiKakuGo-W5', fontSize=8,
                         textColor=GRAY, leading=12, wordWrap='CJK')
S_STEP = ParagraphStyle('JStep', fontName='HeiseiKakuGo-W5', fontSize=10,
                        textColor=DARK, leading=14, wordWrap='CJK')
S_CODE = ParagraphStyle('JCode', fontName='Courier', fontSize=8,
                        textColor=colors.HexColor('#e5e7eb'),
                        backColor=colors.HexColor('#1f2937'),
                        leading=11, leftIndent=8, rightIndent=8,
                        spaceBefore=4, spaceAfter=4)
S_NOTE = ParagraphStyle('JNote', fontName='HeiseiKakuGo-W5', fontSize=9,
                        textColor=DARK, leading=13, wordWrap='CJK',
                        leftIndent=6, rightIndent=6)
S_TH = ParagraphStyle('JTH', fontName='HeiseiKakuGo-W5', fontSize=8.5,
                       textColor=colors.HexColor('#1e3a5f'), leading=12,
                       alignment=TA_CENTER, wordWrap='CJK')
S_TD = ParagraphStyle('JTD', fontName='HeiseiKakuGo-W5', fontSize=8.5,
                       textColor=DARK, leading=12, wordWrap='CJK')


def hr():
    return HRFlowable(width='100%', thickness=1, color=BLUE,
                      spaceBefore=2, spaceAfter=6)


def make_table(headers, rows, col_widths=None):
    """日本語対応テーブル"""
    w = col_widths or [170 * mm / len(headers)] * len(headers)
    data = [[Paragraph(h, S_TH) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), S_TD) for c in row])

    t = Table(data, colWidths=w, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), BG_BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i),
                               colors.HexColor('#f9fafb')))
    t.setStyle(TableStyle(style_cmds))
    return t


def note_box(text, bg=BG_YELLOW):
    """注意/情報ボックス"""
    data = [[Paragraph(text, S_NOTE)]]
    t = Table(data, colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def step(num, text):
    """ステップ番号 + テキスト"""
    data = [[Paragraph(f'<b>{num}</b>', ParagraphStyle(
        'StepNum', fontName='HeiseiKakuGo-W5', fontSize=10,
        textColor=WHITE, alignment=TA_CENTER)),
             Paragraph(text, S_STEP)]]
    t = Table(data, colWidths=[8 * mm, 162 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), LIGHT_BLUE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return t


def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
    )
    story = []
    today = datetime.date.today().strftime('%Y年%m月%d日')

    # ==================== 表紙 ====================
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph('Timebaibai', S_TITLE))
    story.append(Paragraph('新機能ガイド', ParagraphStyle(
        'Cover2', fontName='HeiseiKakuGo-W5', fontSize=22,
        textColor=BLUE, alignment=TA_CENTER, leading=30, spaceAfter=12)))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph('全機能ガイド', S_SUBTITLE))
    story.append(Paragraph('占いサロンチャンス 管理者向け', S_SUBTITLE))
    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph(today, ParagraphStyle(
        'Date', fontName='HeiseiKakuGo-W5', fontSize=11,
        textColor=GRAY, alignment=TA_CENTER)))
    story.append(Paragraph('https://timebaibai.com', ParagraphStyle(
        'URL', fontName='Courier', fontSize=11,
        textColor=GRAY, alignment=TA_CENTER)))
    story.append(PageBreak())

    # ==================== 目次 ====================
    story.append(Paragraph('目次', S_H1))
    story.append(hr())
    toc_items = [
        '1. 機能概要',
        '2. RAGナレッジ管理 — AIの参照データを登録する',
        '3. AI下書き生成 + LLM Judge品質評価',
        '4. 投稿フロー（即時投稿・予約投稿）',
        '5. コスト試算',
        '6. WordPress iframe埋め込み',
        '7. 初期セットアップ手順と日常運用',
        '8. LINE連携機能',
        '9. デモモード切替',
        '10. 自動バックアップ',
    ]
    for item in toc_items:
        story.append(Paragraph(item, ParagraphStyle(
            'TOC', fontName='HeiseiKakuGo-W5', fontSize=12,
            textColor=BLUE, leading=20, leftIndent=10)))
    story.append(PageBreak())

    # ==================== 1. 機能概要 ====================
    story.append(Paragraph('1. 機能概要', S_H1))
    story.append(hr())
    story.append(Paragraph('<b>3つの主要機能</b>', S_H2))
    story.append(make_table(
        ['機能', '概要', '技術'],
        [
            ['RAGナレッジ', 'キャスト・店舗情報をDBに蓄積しAI精度を担保', 'KnowledgeEntry'],
            ['AI下書き+LLM Judge', 'Gemini 2.5 Flashで投稿文自動生成、品質自動評価', 'Gemini API'],
            ['WordPress埋め込み', '予約/シフトをiframeで外部サイトに埋め込み', 'APIキー認証+CSP'],
        ],
        [40 * mm, 75 * mm, 55 * mm],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph('<b>システム全体図</b>', S_H2))
    flow_text = (
        'RAG Knowledge (ナレッジDB)<br/>'
        '　　↓<br/>'
        'Gemini API (AI生成)<br/>'
        '　　↓<br/>'
        'DraftPost (下書き) → LLM Judge (品質評価)<br/>'
        '　　↓<br/>'
        '下書き管理UI (編集・承認・投稿)<br/>'
        '　　↓<br/>'
        'X API / Instagram Browser / GBP Browser'
    )
    story.append(note_box(flow_text, BG_BLUE))
    story.append(PageBreak())

    # ==================== 2. RAGナレッジ ====================
    story.append(Paragraph('2. RAGナレッジ管理', S_H1))
    story.append(hr())
    story.append(Paragraph('<b>目的</b>', S_H2))
    story.append(Paragraph(
        'AIが正確な投稿文を生成するための「事実データベース」です。'
        'キャスト名、得意占術、店舗情報などを登録しておくと、AI生成時に自動で参照されます。',
        S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>操作手順</b>', S_H2))
    story.append(Paragraph('管理画面URL: https://timebaibai.com/admin/', S_SMALL))
    story.append(Spacer(1, 2 * mm))
    story.append(step(1, 'サイドバー →「SNS自動投稿」グループ →「SNSナレッジ」をクリック'))
    story.append(step(2, '右上の「SNSナレッジを追加」ボタンをクリック'))
    story.append(step(3, '店舗・カテゴリ・タイトル・内容を入力して「保存」'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>カテゴリ一覧</b>', S_H3))
    story.append(make_table(
        ['カテゴリ', '用途', '入力例'],
        [
            ['キャストプロフィール', '占い師の情報（名前、得意占術、紹介文）',
             '月華先生: タロット・西洋占星術が得意'],
            ['店舗情報', '住所、営業時間、最寄駅',
             'JR高円寺駅 徒歩3分、11:00-23:00'],
            ['サービス情報', '占術メニュー、料金、所要時間',
             'タロット30分 ¥3,000〜'],
            ['キャンペーン', '期間限定の割引やイベント',
             '4月限定 初回30%OFF'],
            ['カスタム', '上記に当てはまらない自由記述',
             '注意事項、特記事項など'],
        ],
        [35 * mm, 55 * mm, 80 * mm],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(note_box(
        '<b>一括登録のコツ:</b> 既存のナレッジを1つ選択 → アクション「Staffから自動生成」を実行 '
        '→ 全キャストのプロフィールが自動作成されます。', BG_GREEN))
    story.append(PageBreak())

    # ==================== 3. AI下書き + LLM Judge ====================
    story.append(Paragraph('3. AI下書き生成 + LLM Judge評価', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>下書き管理画面の開き方</b>', S_H2))
    story.append(Paragraph(
        'サイドバー →「SNS下書き管理」リンク（またはURL: /admin/social/drafts/）', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>STEP 1: AIに下書きを作らせる</b>', S_H2))
    story.append(step(1, '画面右上の「AI下書き生成」ボタン（紫色）をクリック'))
    story.append(step(2, '生成フォームで「店舗」「対象日」「投稿先（X/Instagram/GBP）」を選択'))
    story.append(step(3, '「生成する」ボタンをクリック → 数秒でAIが投稿文を生成'))
    story.append(step(4, '自動でLLM Judgeが品質スコアを計算し、一覧画面に戻る'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>STEP 2: 生成結果を確認する</b>', S_H2))
    story.append(Paragraph('一覧画面で各下書きカードに表示される情報:', S_BODY))
    story.append(make_table(
        ['表示項目', '説明'],
        [
            ['ステータスバッジ', '生成済み(青) / 予約済み(橙) / 投稿済み(灰) / 却下(赤)'],
            ['品質スコア（星マーク）', '0.7以上=緑(高品質) / 0.4-0.69=黄(標準) / 0.4未満=赤(要改善)'],
            ['プラットフォームアイコン', 'X / Instagram / GBP のアイコンが表示'],
            ['投稿テキスト', 'AI生成された全文がそのまま表示（編集可能）'],
            ['品質フィードバック', 'クリックで展開。LLM Judgeの詳細な評価コメント'],
        ],
        [45 * mm, 125 * mm],
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>STEP 3: 投稿する or 再生成する</b>', S_H2))
    story.append(Paragraph('各カードの右側にあるボタン:', S_BODY))
    story.append(make_table(
        ['ボタン', '色', '動作'],
        [
            ['投稿', '緑', '即座にX/Instagram/GBPに投稿される'],
            ['再生成', '黄', '内容が気に入らなければAIに書き直させる（旧版は却下扱い）'],
        ],
        [30 * mm, 20 * mm, 120 * mm],
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('<b>LLM Judge 評価基準</b>', S_H2))
    story.append(make_table(
        ['チェック項目', '方式', '配点', '内容'],
        [
            ['店舗名チェック', 'ルール（即時）', '−', '店舗名が含まれているか'],
            ['禁止ワード', 'ルール（即時）', '−', '不適切な表現がないか'],
            ['文字数', 'ルール（即時）', '−', 'X向け加重文字数280以内か'],
            ['事実正確性', 'LLM Judge（AI）', '30%', 'キャスト名・占術が正確か'],
            ['文章品質', 'LLM Judge（AI）', '30%', '自然で読みやすい文章か'],
            ['集客効果', 'LLM Judge（AI）', '20%', '来店意欲を喚起できるか'],
            ['プラットフォーム適合', 'LLM Judge（AI）', '20%', 'X/Insta/GBPの特性に合うか'],
        ],
        [38 * mm, 35 * mm, 17 * mm, 80 * mm],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph('<b>品質スコアの目安</b>', S_H3))
    story.append(make_table(
        ['スコア', '評価', '推奨アクション'],
        [
            ['0.80 〜 1.00', '高品質', 'そのまま投稿OK'],
            ['0.60 〜 0.79', '標準', '確認して投稿、必要に応じ微修正'],
            ['0.00 〜 0.59', '要改善', '手動編集 or 「再生成」ボタンで書き直し'],
        ],
        [35 * mm, 30 * mm, 105 * mm],
    ))
    story.append(PageBreak())

    # ==================== 4. 投稿フロー ====================
    story.append(Paragraph('4. 投稿フロー', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>即時投稿</b>', S_H2))
    story.append(step(1, '下書き一覧で「投稿」ボタン（緑）をクリック'))
    story.append(step(2, 'プラットフォームを確認して投稿実行'))
    story.append(step(3, 'X: API経由で投稿 / Instagram・GBP: ブラウザ自動投稿'))
    story.append(step(4, 'ステータスが「投稿済み」に自動変更'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('<b>予約投稿</b>', S_H2))
    story.append(step(1, '下書き一覧で「予約投稿」ボタンをクリック'))
    story.append(step(2, '投稿日時をカレンダーで指定'))
    story.append(step(3, 'ステータスが「予約済み」（橙）に変更'))
    story.append(step(4, 'Celery Beatが5分ごとにチェック → 時刻到達で自動投稿'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('<b>自動生成スケジュール</b>', S_H2))
    story.append(note_box(
        '<b>毎朝08:00</b>にCelery Beatが全店舗の下書きを自動AI生成します。<br/>'
        '管理者は出勤後にチェック → 承認 → 投稿/予約投稿するだけでOK。', BG_BLUE))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('<b>プラットフォーム別投稿方式</b>', S_H2))
    story.append(make_table(
        ['プラットフォーム', '方式', '認証', '制限'],
        [
            ['X (Twitter)', 'API v2 (OAuth 2.0)', '管理画面でOAuth連携', '月500件 (Free)'],
            ['Instagram', 'ブラウザ自動投稿', '初回手動ログイン', '1日1-2件推奨'],
            ['Google Business', 'ブラウザ自動投稿', '初回手動ログイン', '1日1件推奨'],
        ],
        [35 * mm, 40 * mm, 45 * mm, 50 * mm],
    ))
    story.append(PageBreak())

    # ==================== 5. コスト ====================
    story.append(Paragraph('5. コスト試算', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>月間コスト概算（1店舗・1日1投稿の場合）</b>', S_H2))
    story.append(make_table(
        ['項目', '単価', '月間使用量', '月額'],
        [
            ['Gemini 2.5 Flash (生成)', '無料枠: 1500回/日', '約30回', '¥0'],
            ['Gemini 2.5 Flash (Judge)', '同上', '約30回', '¥0'],
            ['X API Free Tier', '無料 (月500件)', '約30件', '¥0'],
            ['Playwright (OSS)', '無料', '−', '¥0'],
            ['EC2 t3.micro (既存)', '約$8.5/月', '常時稼働', '¥1,300 (既存)'],
        ],
        [45 * mm, 45 * mm, 35 * mm, 45 * mm],
    ))
    story.append(Spacer(1, 3 * mm))
    story.append(note_box(
        '<b>結論:</b> 現在の利用規模では追加コストゼロで運用できます。'
        'Gemini API無料枠、X API Free (月500件) の範囲内です。', BG_GREEN))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('<b>スケールアップ時の目安</b>', S_H2))
    story.append(make_table(
        ['規模', 'Gemini API', 'X API', '月額追加コスト'],
        [
            ['1店舗 × 1日1投稿', '無料枠内', 'Free (500/月)', '¥0'],
            ['5店舗 × 1日1投稿', '無料枠内', 'Free (500/月)', '¥0'],
            ['10店舗 × 1日2投稿', 'Pay-as-you-go', 'Basic ($100/月)', '約¥15,000'],
        ],
        [45 * mm, 40 * mm, 40 * mm, 45 * mm],
    ))
    story.append(PageBreak())

    # ==================== 6. WordPress ====================
    story.append(Paragraph('6. WordPress iframe埋め込み', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>概要</b>', S_H2))
    story.append(Paragraph(
        'Timebaibaiの予約カレンダーやシフト表示を、WordPressサイトにiframeで埋め込めます。'
        'timebaibai.com本体には一切影響ありません。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>Step 1: Timebaibai管理画面で有効化</b>', S_H2))
    story.append(step(1, '管理画面 →「メインサイト設定」→「外部埋め込みを有効化」をONにして保存'))
    story.append(step(2, '管理画面 →「店舗一覧」→ 対象店舗を選択'))
    story.append(step(3, 'アクションドロップダウンで「埋め込みAPIキーを生成」→ 実行'))
    story.append(step(4, '（推奨）「埋め込み許可ドメイン」にWordPressサイトのドメインを入力'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>Step 2: WordPressに埋め込みコードを追加</b>', S_H2))
    story.append(Paragraph(
        '固定ページやブロックエディタで「カスタムHTML」ブロックに以下をコピペ:', S_BODY))
    code_html = (
        '&lt;iframe<br/>'
        '  src="https://timebaibai.com/embed/booking/1/?api_key=YOUR_KEY"<br/>'
        '  width="100%" height="600"<br/>'
        '  style="border:none; max-width:100%;"<br/>'
        '  loading="lazy"<br/>'
        '&gt;&lt;/iframe&gt;'
    )
    story.append(note_box(code_html, BG_BLUE))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>埋め込みURL一覧</b>', S_H2))
    story.append(make_table(
        ['URL', '表示内容', '用途'],
        [
            ['/embed/booking/&lt;store_id&gt;/', '予約カレンダー', '顧客が予約スロットを選択'],
            ['/embed/shift/&lt;store_id&gt;/', '本日のシフト', '出勤キャスト一覧を公開表示'],
        ],
        [65 * mm, 40 * mm, 65 * mm],
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>セキュリティ</b>', S_H2))
    story.append(make_table(
        ['脅威', '対策'],
        [
            ['APIキーなし/不正', '403 Forbiddenを返却'],
            ['埋め込み無効時', '404 Not Foundを返却'],
            ['不正ドメインからの埋め込み', 'CSP frame-ancestorsヘッダーで制限'],
            ['他ページのiframe表示', 'X-Frame-Options: DENYを維持（embedパスのみ例外）'],
        ],
        [60 * mm, 110 * mm],
    ))
    story.append(PageBreak())

    # ==================== 7. セットアップ ====================
    story.append(Paragraph('7. 初期セットアップ手順と日常運用', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>SNS自動投稿の初期設定（1回だけ）</b>', S_H2))
    story.append(step(1,
        'Gemini APIキー設定: aistudio.google.com でキーを取得 → EC2の.envファイルに追加'))
    story.append(step(2,
        'ナレッジ登録: 管理画面 → SNSナレッジ → キャスト/店舗/サービス情報を登録'))
    story.append(step(3,
        '下書き生成テスト: SNS下書き管理 →「AI下書き生成」→ AIが文章を生成することを確認'))
    story.append(step(4,
        'X OAuth連携（任意）: SNSアカウント → X連携 → OAuth認証フローを実行'))
    story.append(step(5,
        '投稿テスト: 下書き一覧 →「投稿」ボタン → Xに投稿されることを確認'))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph('<b>日常運用フロー（毎日5分）</b>', S_H2))
    story.append(note_box(
        '<b>毎朝の流れ:</b><br/>'
        '08:00 — Celeryが自動で下書きを生成<br/>'
        '出勤後 — 管理画面で「SNS下書き管理」を開く<br/>'
        'AIが作った投稿文を確認 → 問題なければ「投稿」ボタンを押す<br/>'
        '（または投稿日時を指定して「予約投稿」する）<br/><br/>'
        '<b>これだけで毎日のSNS投稿が完了します。</b>', BG_GREEN))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph('<b>注意事項</b>', S_H2))
    story.append(note_box(
        '・Gemini API無料枠: 15リクエスト/分、1日1500リクエスト<br/>'
        '・X API Free: 月500件まで（超過時は翌月リセット）<br/>'
        '・Instagram/GBP ブラウザ投稿: 1日1-2件推奨（BAN防止）<br/>'
        '・ブラウザ投稿を使う場合、EC2にPlaywrightのインストールが必要',
        BG_YELLOW))

    # ==================== 8. LINE連携機能 ====================
    story.append(PageBreak())
    story.append(Paragraph('8. LINE連携機能', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>概要</b>', S_H2))
    story.append(Paragraph(
        'LINE公式アカウントを通じて予約受付、リマインダー送信、セグメント配信を自動化します。'
        'すべてフィーチャーフラグで個別にON/OFF制御できます。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>機能一覧</b>', S_H2))
    story.append(make_table(
        ['機能', 'フラグ', '説明'],
        [
            ['Webhook受信', '常時有効', '友だち追加/ブロック検知、メッセージ/Postback受信'],
            ['チャットボット予約', 'line_chatbot_enabled', 'LINEトーク内で店舗→スタッフ→日時→予約確定'],
            ['リマインダー', 'line_reminder_enabled', '前日18:00 / 当日2時間前に自動LINE通知'],
            ['セグメント配信', 'line_segment_enabled', '新規/リピーター/VIP/休眠 別一括配信'],
            ['リッチメニュー', '常時有効', '予約する/予約確認/お問い合わせのPostback対応'],
            ['仮予約確認', '常時有効', '管理画面から予約の確定/却下 + LINE通知'],
        ],
        [40 * mm, 45 * mm, 85 * mm],
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>フラグ設定方法</b>', S_H2))
    story.append(step(1, '管理画面 →「メインサイト設定」を開く'))
    story.append(step(2, '「LINE連携」セクションまでスクロール'))
    story.append(step(3, '必要なフラグをONにして「保存」'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>チャットボット予約フロー</b>', S_H2))
    story.append(note_box(
        '1. 顧客がLINEリッチメニュー「予約する」をタップ<br/>'
        '2. 店舗一覧から選択<br/>'
        '3. スタッフ一覧から選択<br/>'
        '4. カレンダーから日付選択<br/>'
        '5. 空き時間枠から選択<br/>'
        '6. 確認画面で「予約確定」<br/>'
        '7. 予約完了メッセージ + QRコード受信', BG_BLUE))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>セグメント配信</b>', S_H2))
    story.append(make_table(
        ['セグメント', '条件', '配信例'],
        [
            ['新規', '初回予約から30日以内', '初来店ありがとうクーポン'],
            ['リピーター', '2回以上来店、直近90日内', '常連様限定メニュー案内'],
            ['VIP', '5回以上来店', 'VIP限定イベント招待'],
            ['休眠', '最終来店90日以上前', 'お久しぶり割引クーポン'],
        ],
        [30 * mm, 55 * mm, 85 * mm],
    ))

    # ==================== 9. デモモード切替 ====================
    story.append(PageBreak())
    story.append(Paragraph('9. デモモード切替', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>概要</b>', S_H2))
    story.append(Paragraph(
        'デモモードをONにすると、ダッシュボードにデモデータ（模擬データ）も表示されます。'
        'OFFにすると実データのみ表示。営業デモや機能紹介に活用できます。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>設定方法</b>', S_H2))
    story.append(step(1, '管理画面 →「メインサイト設定」を開く'))
    story.append(step(2, '「デモモード」セクションまでスクロール'))
    story.append(step(3, '「デモモード」チェックボックスをON/OFFにして「保存」'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>動作の違い</b>', S_H2))
    story.append(make_table(
        ['設定', 'ダッシュボード表示', 'バナー'],
        [
            ['デモモードON', 'デモデータ + 実データの両方を表示', '「DEMO MODE」バナーが表示される'],
            ['デモモードOFF（デフォルト）', '実データのみ表示', 'バナーなし（通常運用）'],
        ],
        [45 * mm, 80 * mm, 45 * mm],
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>デモデータ自動生成</b>', S_H2))
    story.append(Paragraph(
        'デモモードON時、30分ごとにCeleryが当日分のデモ注文・予約・来客数を自動生成します。'
        '手動生成も可能:', S_BODY))
    story.append(note_box(
        'python manage.py generate_live_demo_data', BG_BLUE))
    story.append(Spacer(1, 3 * mm))

    story.append(note_box(
        '<b>注意:</b> デモデータは is_demo=True フラグで管理されています。'
        'デモモードOFF時にダッシュボードから自動的に除外されるため、'
        '実際の売上データに影響はありません。', BG_YELLOW))

    # ==================== 10. 自動バックアップ ====================
    story.append(PageBreak())
    story.append(Paragraph('10. 自動バックアップ', S_H1))
    story.append(hr())

    story.append(Paragraph('<b>概要</b>', S_H2))
    story.append(Paragraph(
        'SQLiteデータベースのアトミックバックアップを管理画面から設定・実行できます。'
        'S3へのアップロード、ローカル保持ポリシー、LINE通知に対応しています。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>バックアップ設定</b>', S_H2))
    story.append(step(1, '管理画面 →「バックアップ設定」を開く'))
    story.append(step(2, 'バックアップ間隔を選択（OFF / 毎分 / 毎時 / 毎日）'))
    story.append(step(3, 'S3アップロード、保持数、LINE通知を設定して「保存」'))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>設定項目一覧</b>', S_H2))
    story.append(make_table(
        ['項目', 'デフォルト', '説明'],
        [
            ['バックアップ間隔', 'OFF', 'off / 毎分 / 毎時 / 毎日'],
            ['S3アップロード', 'ON', 'バックアップファイルをS3に自動アップロード'],
            ['S3バケット', 'mee-newfuhi-backups', 'アップロード先S3バケット名'],
            ['ローカル保持数', '30', 'ローカルに保持するバックアップファイル数'],
            ['S3保持日数', '90', 'S3上のバックアップ保持日数'],
            ['LINE通知', 'ON', 'バックアップ完了/失敗時にLINE Notify通知'],
        ],
        [40 * mm, 40 * mm, 90 * mm],
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>手動バックアップ</b>', S_H2))
    story.append(Paragraph('管理画面から:', S_BODY))
    story.append(step(1, '管理画面 →「バックアップ設定」を開く'))
    story.append(step(2, '右上の「手動バックアップ実行」ボタンをクリック'))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph('コマンドラインから:', S_BODY))
    story.append(note_box('python manage.py create_backup', BG_BLUE))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('<b>バックアップ履歴</b>', S_H2))
    story.append(Paragraph(
        '管理画面 →「バックアップ履歴」で過去のバックアップ実行結果を確認できます。'
        'ステータス（成功/失敗/実行中）、ファイルサイズ、S3アップロード状況、'
        'エラーメッセージが一覧表示されます。', S_BODY))

    # ビルド
    doc.build(story)
    print(f'PDF generated: {output_path}')


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'timebaibai_feature_guide.pdf')
    build_pdf(out)
