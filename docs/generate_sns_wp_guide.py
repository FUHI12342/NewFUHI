#!/usr/bin/env python3
"""SNS自動投稿 + WordPress埋め込み 操作ガイド PDF — ReportLab CIDフォント版"""
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
    PageBreak, HRFlowable, ListFlowable, ListItem, Image,
)

# CIDフォント登録
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))

BLUE = colors.HexColor('#1e40af')
LIGHT_BLUE = colors.HexColor('#3b82f6')
DARK = colors.HexColor('#1a1a1a')
GRAY = colors.HexColor('#6b7280')
BG_BLUE = colors.HexColor('#eff6ff')
BG_GREEN = colors.HexColor('#ecfdf5')
BG_YELLOW = colors.HexColor('#fef3c7')
BG_PURPLE = colors.HexColor('#f5f3ff')
BG_RED = colors.HexColor('#fef2f2')
WHITE = colors.white
GREEN = colors.HexColor('#059669')
PURPLE = colors.HexColor('#7c3aed')
RED = colors.HexColor('#dc2626')

# スタイル定義
S_TITLE = ParagraphStyle('JTitle', fontName='HeiseiKakuGo-W5', fontSize=26,
                         textColor=BLUE, alignment=TA_CENTER, leading=34,
                         spaceAfter=6)
S_SUBTITLE = ParagraphStyle('JSub', fontName='HeiseiKakuGo-W5', fontSize=14,
                            textColor=GRAY, alignment=TA_CENTER, leading=20,
                            spaceAfter=4)
S_H1 = ParagraphStyle('JH1', fontName='HeiseiKakuGo-W5', fontSize=18,
                       textColor=BLUE, leading=24, spaceAfter=8, spaceBefore=12)
S_H2 = ParagraphStyle('JH2', fontName='HeiseiKakuGo-W5', fontSize=13,
                       textColor=colors.HexColor('#1e3a5f'), leading=18,
                       spaceAfter=6, spaceBefore=10)
S_H3 = ParagraphStyle('JH3', fontName='HeiseiKakuGo-W5', fontSize=11,
                       textColor=DARK, leading=15, spaceAfter=4, spaceBefore=8)
S_BODY = ParagraphStyle('JBody', fontName='HeiseiKakuGo-W5', fontSize=9.5,
                        textColor=DARK, leading=15, spaceAfter=4, wordWrap='CJK')
S_SMALL = ParagraphStyle('JSmall', fontName='HeiseiKakuGo-W5', fontSize=8,
                         textColor=GRAY, leading=12, spaceAfter=2, wordWrap='CJK')
S_CODE = ParagraphStyle('JCode', fontName='HeiseiKakuGo-W5', fontSize=8.5,
                        textColor=DARK, leading=13, spaceAfter=4,
                        leftIndent=12, wordWrap='CJK')
S_STEP_NUM = ParagraphStyle('StepNum', fontName='HeiseiKakuGo-W5', fontSize=9.5,
                            textColor=WHITE, alignment=TA_CENTER)
S_NOTE = ParagraphStyle('JNote', fontName='HeiseiKakuGo-W5', fontSize=9,
                        textColor=colors.HexColor('#92400e'), leading=14,
                        spaceAfter=4, wordWrap='CJK')
S_WARN = ParagraphStyle('JWarn', fontName='HeiseiKakuGo-W5', fontSize=9,
                        textColor=RED, leading=14, spaceAfter=4, wordWrap='CJK')


SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')


def screenshot_image(filename, caption='', max_width=170 * mm):
    """スクリーンショットを適切なサイズで挿入"""
    path = os.path.join(SCREENSHOTS_DIR, filename)
    if not os.path.exists(path):
        return Paragraph(f'[スクリーンショット: {filename} が見つかりません]', S_SMALL)

    from reportlab.lib.utils import ImageReader
    img_reader = ImageReader(path)
    iw, ih = img_reader.getSize()
    aspect = ih / iw
    width = min(max_width, 170 * mm)
    height = width * aspect
    # 高さが200mmを超える場合は縮小
    if height > 200 * mm:
        height = 200 * mm
        width = height / aspect

    elements = []
    elements.append(Image(path, width=width, height=height))
    if caption:
        elements.append(Paragraph(caption, ParagraphStyle(
            'Caption', fontName='HeiseiKakuGo-W5', fontSize=8,
            textColor=GRAY, alignment=TA_CENTER, spaceAfter=4, spaceBefore=2)))
    return elements


def add_screenshot(story, filename, caption=''):
    """story にスクリーンショットを追加"""
    result = screenshot_image(filename, caption)
    if isinstance(result, list):
        # 画像をボーダー付きテーブルに入れる
        img_table = Table([[result[0]]], colWidths=[172 * mm])
        img_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e5e7eb')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(img_table)
        if len(result) > 1:
            story.append(result[1])  # caption
    else:
        story.append(result)
    story.append(Spacer(1, 3 * mm))


def note_box(text, bg=BG_YELLOW):
    """注意ボックス"""
    style = S_NOTE if bg == BG_YELLOW else ParagraphStyle(
        'NoteAlt', parent=S_NOTE, textColor=DARK)
    t = Table([[Paragraph(text, style)]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    return t


def step_box(number, title, description):
    """手順ステップボックス"""
    num_p = Paragraph(str(number), S_STEP_NUM)
    num_t = Table([[num_p]], colWidths=[22], rowHeights=[22])
    num_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLUE),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
    ]))

    title_p = Paragraph(f'<b>{title}</b>', S_BODY)
    desc_p = Paragraph(description, S_SMALL)

    content = Table([[title_p], [desc_p]], colWidths=[148 * mm])
    content.setStyle(TableStyle([
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))

    row = Table([[num_t, content]], colWidths=[28, 150 * mm])
    row.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return row


def build_pdf():
    output_path = os.path.join(os.path.dirname(__file__), 'sns_wp_guide.pdf')
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    story = []

    # ============================================================
    # 表紙
    # ============================================================
    story.append(Spacer(1, 40 * mm))
    story.append(Paragraph('Timebaibai', S_TITLE))
    story.append(Paragraph('SNS自動投稿 &amp; WordPress埋め込み', S_TITLE))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph('操作・設定ガイド', S_SUBTITLE))
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width='60%', color=BLUE, thickness=2))
    story.append(Spacer(1, 8 * mm))
    today = datetime.date.today().strftime('%Y年%m月%d日')
    story.append(Paragraph(f'最終更新: {today}', S_SMALL))
    story.append(Paragraph('https://timebaibai.com', S_SMALL))
    story.append(Spacer(1, 20 * mm))

    # 目次
    story.append(Paragraph('目次', S_H2))
    toc_items = [
        ('第1章', 'SNS自動投稿機能 — 概要'),
        ('第2章', 'AI下書き生成の使い方'),
        ('第3章', 'プラットフォーム別ルール'),
        ('第4章', '品質評価（LLM Judge）'),
        ('第5章', '投稿方法（API / ブラウザ）'),
        ('第6章', 'RAGナレッジベース管理'),
        ('第7章', 'WordPress埋め込み — 概要'),
        ('第8章', 'ショートコード設定手順'),
        ('第9章', 'セキュリティとトラブルシューティング'),
    ]
    for ch, title in toc_items:
        story.append(Paragraph(f'{ch}　{title}', S_BODY))
    story.append(PageBreak())

    # ============================================================
    # 第1章: SNS自動投稿 概要
    # ============================================================
    story.append(Paragraph('第1章　SNS自動投稿機能 — 概要', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'Timebaibaiは、Gemini AI を活用して各SNSプラットフォーム向けの投稿文を自動生成し、'
        'ワンクリックで投稿できる機能を搭載しています。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('システム構成図', S_H3))
    arch_data = [
        ['コンポーネント', '役割', '技術'],
        ['RAGナレッジ', 'キャスト情報・店舗情報を蓄積', 'Django ORM + Staff.introduction'],
        ['AI生成エンジン', 'プラットフォーム別投稿文を生成', 'Gemini 2.5-flash API'],
        ['LLM Judge', '品質スコアリング (0.0〜1.0)', 'Gemini 2.5-flash (評価用)'],
        ['下書き管理UI', '編集・承認・投稿操作', 'Django Admin カスタムビュー'],
        ['投稿ディスパッチャー', 'API or ブラウザで投稿実行', 'X API v2 / Playwright'],
    ]
    t = Table(arch_data, colWidths=[42 * mm, 60 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('対応プラットフォーム', S_H3))
    pf_data = [
        ['プラットフォーム', '投稿方法', '文字数上限', '特徴'],
        ['X (Twitter)', 'API投稿 / ブラウザ投稿', '加重280文字', '簡潔・ハッシュタグ1-2個'],
        ['Instagram', 'ブラウザ投稿のみ', '2,200文字', '段落分け・ハッシュタグ5-10個'],
        ['Google Business Profile', 'ブラウザ投稿のみ', '1,500文字', 'ビジネス文体・箇条書き'],
    ]
    t = Table(pf_data, colWidths=[38 * mm, 40 * mm, 32 * mm, 52 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ============================================================
    # 第2章: AI下書き生成の使い方
    # ============================================================
    story.append(Paragraph('第2章　AI下書き生成の使い方', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('アクセス方法', S_H3))
    story.append(Paragraph(
        '管理画面サイドバー → 「SNS投稿」→「SNS下書き管理」を選択します。', S_BODY))
    story.append(Paragraph(
        'URL: https://timebaibai.com/admin/social/drafts/', S_CODE))
    story.append(Spacer(1, 3 * mm))

    # スクリーンショット: 下書き一覧
    add_screenshot(story, '01_draft_list.png', '図2-1: SNS下書き管理 一覧画面')

    story.append(Paragraph('AI下書き生成手順', S_H3))
    story.append(step_box(1, '「AI下書き生成」ボタンをクリック',
                          '画面右上の紫色のボタンです'))
    story.append(step_box(2, '生成設定を入力',
                          '店舗を選択 → 対象日を指定 → プラットフォームを選択（X / Instagram / GBP）'))
    story.append(step_box(3, '「生成」をクリック',
                          'Gemini AI がプラットフォーム別ルールに従い投稿文を自動生成します'))
    story.append(step_box(4, '品質スコアを確認',
                          'LLM Judge が 0.0〜1.0 で品質評価。0.7以上が推奨ラインです'))
    story.append(step_box(5, '必要に応じて編集',
                          '「編集」ボタンで内容修正可能。保存時に自動で再評価されます'))
    story.append(Spacer(1, 3 * mm))

    # スクリーンショット: AI下書き生成フォーム
    add_screenshot(story, '03_generate_form.png', '図2-2: AI下書き生成フォーム')

    story.append(note_box(
        '注意: Gemini API キーが settings の GEMINI_API_KEY に設定されている必要があります。'
        '無料枠では gemini-2.5-flash モデルが使用されます。'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('下書き編集機能', S_H3))
    story.append(Paragraph(
        '各下書きカードの「編集」ボタンをクリックすると、以下が表示されます:', S_BODY))

    # スクリーンショット: 下書き編集モード
    add_screenshot(story, '02_draft_edit.png', '図2-3: 下書きインライン編集モード')
    edit_data = [
        ['要素', '説明'],
        ['テキストエリア', '投稿内容をリアルタイムで編集可能'],
        ['プラットフォーム選択', 'X / Instagram / GBP のチェックボックスで投稿先を変更'],
        ['文字数カウンター', 'プラットフォーム別の文字数をリアルタイム表示（超過時は赤色）'],
        ['保存ボタン', '保存と同時に品質スコアが再評価されます'],
    ]
    t = Table(edit_data, colWidths=[42 * mm, 125 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ============================================================
    # 第3章: プラットフォーム別ルール
    # ============================================================
    story.append(Paragraph('第3章　プラットフォーム別AI生成ルール', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'AIは選択されたプラットフォームに応じて、異なるルールで投稿文を生成します。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    # X ルール
    story.append(Paragraph('X (Twitter) 生成ルール', S_H2))
    x_rules = [
        ['ルール', '詳細'],
        ['文字数', '加重280文字以内（全角=2, 半角=1, 絵文字=2）'],
        ['改行', '最小限（1〜2回まで）。段落分けはしない'],
        ['文体', 'コンパクトで一息で読める文章'],
        ['絵文字', '2〜3個にとどめ、テキスト中に自然に配置'],
        ['ハッシュタグ', '1〜2個のみ、末尾に配置'],
        ['リンク', '不要（URLは後から追加される）'],
    ]
    t = Table(x_rules, colWidths=[30 * mm, 138 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    # Instagram ルール
    story.append(Paragraph('Instagram 生成ルール', S_H2))
    ig_rules = [
        ['ルール', '詳細'],
        ['文字数', '2,200文字以内'],
        ['構成', '3〜5段落（導入 → キャスト紹介 → サービス → CTA）'],
        ['改行', '段落ごとに空行を入れる（読みやすさ重視）'],
        ['絵文字', '豊富に使用（各段落の先頭や文中に配置）'],
        ['ハッシュタグ', '5〜10個、末尾にブロック配置'],
        ['1行目', '注目を引くキャッチコピー（絵文字付き）'],
    ]
    t = Table(ig_rules, colWidths=[30 * mm, 138 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#c026d3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_PURPLE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    # GBP ルール
    story.append(Paragraph('Google Business Profile 生成ルール', S_H2))
    gbp_rules = [
        ['ルール', '詳細'],
        ['文字数', '1,500文字以内'],
        ['文体', 'ビジネス寄りのフォーマルな文章'],
        ['構成', '箇条書きを活用。セクション分け（出勤/サービス/予約方法）'],
        ['絵文字', '控えめ（0〜2個）'],
        ['ハッシュタグ', '不要'],
        ['末尾', '営業時間・アクセス情報・明確なCTA'],
    ]
    t = Table(gbp_rules, colWidths=[30 * mm, 138 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ============================================================
    # 第4章: 品質評価
    # ============================================================
    story.append(Paragraph('第4章　品質評価（LLM Judge）', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'AI生成された下書きは、2段階の品質チェックを自動で受けます。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('評価フロー', S_H3))
    story.append(step_box(1, 'ルールベースチェック（即時・同期）',
                          'プラットフォーム別文字数超過、禁止ワード、店舗名チェック、ハッシュタグ数'))
    story.append(step_box(2, 'LLM Judge チェック（Gemini Flash）',
                          '事実正確性(30%)・文章品質(30%)・集客効果(20%)・プラットフォーム適合(20%)'))
    story.append(step_box(3, 'スコア統合',
                          'LLMスコア - ルール減点 = 最終スコア (0.0〜1.0)'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('スコアの目安', S_H3))
    score_data = [
        ['スコア範囲', '判定', '推奨アクション'],
        ['0.70 〜 1.00', '良好（緑）', 'そのまま投稿OK'],
        ['0.40 〜 0.69', '要確認（黄）', '内容を確認し、必要に応じて編集'],
        ['0.00 〜 0.39', '要修正（赤）', '再生成または手動で大幅修正'],
    ]
    t = Table(score_data, colWidths=[35 * mm, 40 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (0, 1), BG_GREEN),
        ('BACKGROUND', (0, 2), (0, 2), BG_YELLOW),
        ('BACKGROUND', (0, 3), (0, 3), BG_RED),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('ルールベースチェック項目', S_H3))
    rule_data = [
        ['チェック項目', 'プラットフォーム', '減点'],
        ['加重文字数超過 (280)', 'X', '-0.20'],
        ['文字数超過 (2,200)', 'Instagram', '-0.15'],
        ['文字数超過 (1,500)', 'GBP', '-0.15'],
        ['空コンテンツ', '全て', '-1.00'],
        ['禁止ワード検出', '全て', '-0.30/個'],
        ['店舗名なし', '全て', '-0.10'],
        ['ハッシュタグ不足 (<3個)', 'Instagram', '-0.05'],
    ]
    t = Table(rule_data, colWidths=[50 * mm, 42 * mm, 25 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ============================================================
    # 第5章: 投稿方法
    # ============================================================
    story.append(Paragraph('第5章　投稿方法（API / ブラウザ）', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        '下書き一覧の各カードには「API投稿」と「ブラウザ投稿」の2つのボタンがあります。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    # スクリーンショット: SNSアカウント
    add_screenshot(story, '06_social_accounts.png', '図5-1: SNSアカウント管理画面')

    # API投稿
    story.append(Paragraph('API投稿（緑ボタン）', S_H2))
    story.append(Paragraph(
        'X (Twitter) のみ対応。OAuth 2.0 PKCE で認証し、X API v2 経由で投稿します。'
        '公式APIのため、BANリスクはありません。', S_BODY))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph('API投稿の設定手順', S_H3))
    story.append(step_box(1, 'X Developer Portal でアプリを作成',
                          'developer.x.com にアクセスし、Free tier で新規プロジェクト作成'))
    story.append(step_box(2, 'OAuth 2.0 設定',
                          'User Authentication → Type: Web App → Callback URL を設定'))
    story.append(step_box(3, '管理画面で「Xアカウント連携」',
                          'SNS投稿 → SNSアカウント → 「X連携」ボタンをクリック'))
    story.append(step_box(4, 'Xログインして認可',
                          'リダイレクト先でアクセス許可 → トークンが自動保存されます'))
    story.append(Spacer(1, 3 * mm))
    story.append(note_box('Free tier の制限: 月500投稿まで。レート制限は自動管理されます。'))
    story.append(Spacer(1, 4 * mm))

    # ブラウザ投稿
    story.append(Paragraph('ブラウザ投稿（紫ボタン）', S_H2))
    story.append(Paragraph(
        'Playwright（ヘッドレスブラウザ）で実際のWebブラウザを自動操作して投稿します。'
        'X / Instagram / GBP の全プラットフォームに対応。', S_BODY))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph('ブラウザ投稿の仕組み', S_H3))
    browser_data = [
        ['動作', '詳細'],
        ['タイピング', '人間らしい速度で1文字ずつ入力（30ms/文字 + ランダムジッタ）'],
        ['ランダム遅延', '各操作間に1〜3秒のランダム待機'],
        ['セッション保持', 'Cookie/LocalStorage を保存し、再ログイン不要'],
        ['スクリーンショット', '投稿後にデバッグ用スクリーンショットを自動保存'],
    ]
    t = Table(browser_data, colWidths=[35 * mm, 133 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PURPLE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_PURPLE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph('初回セットアップ（サーバー上で実行）', S_H3))
    story.append(step_box(1, 'Playwright をインストール',
                          'pip install playwright && playwright install chromium --with-deps'))
    story.append(step_box(2, 'ヘッドあり（GUI）でブラウザを起動',
                          'サーバーにSSHしてXフォワーディング or VNC で GUI 環境を用意'))
    story.append(step_box(3, '各プラットフォームに手動ログイン',
                          'X.com / Instagram / business.google.com にログイン'))
    story.append(step_box(4, 'セッション保存',
                          'ログイン後に自動で storage_state.json が保存されます'))
    story.append(Spacer(1, 3 * mm))

    story.append(note_box(
        'BANリスク: Instagram は高リスク（1日1投稿推奨）。X ブラウザ投稿は中〜高リスク'
        '（API投稿推奨）。GBP は低〜中リスク。', BG_RED))
    story.append(PageBreak())

    # ============================================================
    # 第6章: RAGナレッジ
    # ============================================================
    story.append(Paragraph('第6章　RAGナレッジベース管理', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'AI生成の精度を上げるために、店舗・キャスト情報をナレッジベースに登録します。'
        '登録情報は投稿生成時にRAGコンテキストとしてGeminiに渡されます。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    # スクリーンショット: ナレッジ管理
    add_screenshot(story, '04_knowledge_list.png', '図6-1: SNSナレッジ管理画面')

    story.append(Paragraph('ナレッジカテゴリ', S_H3))
    kg_data = [
        ['カテゴリ', '用途', '例'],
        ['キャストプロフィール', '占い師の紹介文', '○○先生: タロット歴10年、恋愛相談が得意'],
        ['店舗情報', '住所・営業時間等', '渋谷駅徒歩5分、10:00-22:00'],
        ['サービス情報', 'メニュー・料金', 'タロット30分 3,000円'],
        ['キャンペーン', '期間限定情報', '春の新規割引 20% OFF'],
        ['カスタム', '自由記述', '投稿トーンの指示等'],
    ]
    t = Table(kg_data, colWidths=[38 * mm, 42 * mm, 88 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('自動コンテキスト構築', S_H3))
    story.append(Paragraph(
        'AI生成時に以下の情報が自動でプロンプトに含まれます:', S_BODY))
    ctx_data = [
        ['情報源', '内容'],
        ['Store モデル', '店舗名、住所、営業時間、最寄り駅、紹介文'],
        ['Staff.introduction', '各キャストの紹介文（プロフィール欄から自動取得）'],
        ['KnowledgeEntry', '管理画面で登録したナレッジ情報'],
        ['ShiftAssignment', '当日の出勤キャスト名と時間帯'],
    ]
    t = Table(ctx_data, colWidths=[40 * mm, 128 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))
    story.append(note_box(
        'ヒント: Staff（キャスト）の「紹介文」フィールドに詳しいプロフィールを書くと、'
        'AI生成の精度が大幅に向上します。ナレッジ登録不要で自動取得されます。', BG_GREEN))
    story.append(PageBreak())

    # ============================================================
    # 第7章: WordPress埋め込み 概要
    # ============================================================
    story.append(Paragraph('第7章　WordPress埋め込み — 概要', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        'WordPressサイトにTimebaibaiの予約カレンダーやシフト表をiframeで埋め込めます。'
        'ショートコードを使うことで、HTMLの知識不要で設置できます。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    # スクリーンショット: 予約カレンダー埋め込み
    add_screenshot(story, '08_embed_booking.png', '図7-1: 予約カレンダー埋め込みビュー')
    add_screenshot(story, '09_embed_shift.png', '図7-2: シフト表示埋め込みビュー（出勤キャスト表示）')

    story.append(Paragraph('共有用デモページ', S_H2))
    story.append(Paragraph(
        '予約カレンダーとシフト表示を1ページにまとめたデモページを公開しています。'
        'このURLを共有するだけで、埋め込みの実際の動作を確認できます。', S_BODY))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        'デモURL: https://timebaibai.com/embed/demo/', S_CODE))
    story.append(Spacer(1, 2 * mm))
    add_screenshot(story, '10_embed_demo.png', '図7-3: 共有用デモページ（予約+シフト一覧）')
    story.append(note_box(
        'デモページは embed_api_key が設定されている最初の店舗を自動で使用します。'
        'embed_enabled=True の場合のみ表示されます。', BG_GREEN))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('埋め込み可能なビュー', S_H3))
    embed_data = [
        ['パス', 'URL', '内容'],
        ['予約カレンダー', '/embed/booking/<store_id>/', '占い師選択+予約フォーム'],
        ['シフト表示', '/embed/shift/<store_id>/', '本日の出勤キャスト一覧（読み取り専用）'],
        ['デモページ', '/embed/demo/', '予約+シフトを1ページに統合（共有用）'],
    ]
    t = Table(embed_data, colWidths=[35 * mm, 55 * mm, 77 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('仕組み', S_H3))
    story.append(Paragraph(
        'WordPress → ショートコード → iframe → Timebaibai embed ビュー', S_CODE))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        'embed ビューはナビゲーション/ヘッダーなしの最小HTMLで、'
        'Tailwind CSS で自動スタイリングされます。'
        'X-Frame-Options: DENY は embed パスのみ例外（他は DENY 維持）。', S_BODY))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('セキュリティ', S_H3))
    sec_data = [
        ['対策', '詳細'],
        ['APIキー認証', '?api_key= パラメータで Store.embed_api_key と照合'],
        ['グローバル無効化', 'SiteSettings.embed_enabled=False で全体を404に'],
        ['ドメイン制限', 'embed_allowed_domains に許可ドメインを設定 → CSP frame-ancestors'],
        ['iframe例外', '/embed/* パスのみ @xframe_options_exempt（他は DENY）'],
    ]
    t = Table(sec_data, colWidths=[35 * mm, 133 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(PageBreak())

    # ============================================================
    # 第8章: ショートコード設定手順
    # ============================================================
    story.append(Paragraph('第8章　ショートコード設定手順', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('Step A: Timebaibai側の設定', S_H2))

    # スクリーンショット: サイト設定
    add_screenshot(story, '07_site_settings.png', '図8-1: サイト設定 — 埋め込み有効化')

    story.append(step_box(1, 'embed 機能を有効化',
                          '管理画面 → サイト設定 → 「外部埋め込みを有効化」をON'))
    story.append(step_box(2, '店舗にAPIキーを発行',
                          '管理画面 → 店舗一覧 → 対象店舗を選択 → 「外部埋め込み」セクション → '
                          '「APIキー生成」アクションを実行'))

    # スクリーンショット: 店舗設定 embed
    add_screenshot(story, '05_store_embed.png', '図8-2: 店舗設定 — 埋め込みAPIキーセクション')
    story.append(step_box(3, '許可ドメインを設定（任意）',
                          '「埋め込み許可ドメイン」に WordPress サイトのドメインを入力\n'
                          '例: https://your-wordpress-site.com'))
    story.append(step_box(4, 'APIキーをメモ',
                          '生成された embed_api_key を控えておく（ショートコードで使用）'))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('Step B: WordPress側の設定', S_H2))
    story.append(step_box(1, 'functions.php にショートコードを追加',
                          'WordPress管理画面 → 外観 → テーマファイルエディタ → functions.php'))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph('追加するコード（functions.phpの末尾にコピペ）:', S_H3))
    code_text = (
        '// 予約カレンダー\n'
        'function newfuhi_booking_shortcode($atts) {\n'
        '    $atts = shortcode_atts(array(\n'
        "        'store_id' =&gt; '1',\n"
        "        'api_key'  =&gt; '',\n"
        "        'height'   =&gt; '600',\n"
        '    ), $atts);\n'
        '    $src = "https://timebaibai.com/embed/booking/"\n'
        '         . intval($atts["store_id"])\n'
        '         . "/?api_key=" . $atts["api_key"];\n'
        '    return \'&lt;iframe src="\' . esc_url($src) . \'"\n'
        '        width="100%" height="\' . $atts["height"]\n'
        '        . \'px" style="border:none;"&gt;&lt;/iframe&gt;\';\n'
        '}\n'
        "add_shortcode('newfuhi_booking',\n"
        "    'newfuhi_booking_shortcode');\n\n"
        '// シフト表示も同様に追加可能\n'
        "// add_shortcode('newfuhi_shift', ...);"
    )
    story.append(note_box(code_text, BG_BLUE))
    story.append(Spacer(1, 3 * mm))

    story.append(step_box(2, 'ページにショートコードを設置',
                          '投稿/固定ページの編集画面でショートコードブロックを追加'))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph('ショートコードの書き方:', S_H3))
    sc_data = [
        ['用途', 'ショートコード'],
        ['予約カレンダー', '[newfuhi_booking store_id="1" api_key="あなたのAPIキー"]'],
        ['シフト表示', '[newfuhi_shift store_id="1" api_key="あなたのAPIキー"]'],
        ['高さ変更', '[newfuhi_booking store_id="1" api_key="xxx" height="800"]'],
    ]
    t = Table(sc_data, colWidths=[35 * mm, 133 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 3 * mm))

    story.append(step_box(3, 'プレビューで確認',
                          'ページを公開/プレビューし、iframe が正しく表示されることを確認'))
    story.append(Spacer(1, 3 * mm))

    story.append(note_box(
        'ヒント: ショートコードファイルの完全版は docs/wordpress/newfuhi-embed.php に'
        'あります。functions.php にコピペするだけで動作します。', BG_GREEN))
    story.append(PageBreak())

    # ============================================================
    # 第9章: トラブルシューティング
    # ============================================================
    story.append(Paragraph('第9章　セキュリティとトラブルシューティング', S_H1))
    story.append(HRFlowable(width='100%', color=LIGHT_BLUE, thickness=1))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph('管理画面の機能表示制御', S_H3))
    story.append(Paragraph(
        'サイト設定で各管理画面セクションの表示/非表示を切り替えられます。'
        'スーパーユーザーはトグル設定に関わらず常に全機能が表示されます。'
        'デフォルトでは「シフト」と「予約管理」のみ表示されます。', S_BODY))
    story.append(Spacer(1, 3 * mm))
    toggle_data = [
        ['設定項目', 'デフォルト', '説明'],
        ['シフト/予約管理', 'ON', '常時表示（コア機能）'],
        ['タイムカード/POS/在庫等', 'OFF', 'サイト設定で個別にON可能'],
        ['SNS投稿/セキュリティ等', 'OFF', 'サイト設定で個別にON可能'],
        ['スーパーユーザー', '全表示', 'トグルに関わらず常に全機能表示'],
    ]
    t = Table(toggle_data, colWidths=[40 * mm, 28 * mm, 100 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_GREEN),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph('よくある問題と解決策', S_H3))
    ts_data = [
        ['症状', '原因', '解決策'],
        ['AI生成が失敗する', 'GEMINI_API_KEY 未設定 or 無効',
         '.env に GEMINI_API_KEY を設定。Free tier は gemini-2.5-flash のみ対応'],
        ['品質スコアが表示されない', 'Gemini API レート制限',
         '数分待って再実行。1分あたり60リクエスト制限あり'],
        ['iframe が表示されない', 'embed_enabled=False or APIキー不一致',
         'サイト設定で「埋め込み有効化」ON + 店舗のAPIキーを確認'],
        ['iframe に「拒否されました」', 'X-Frame-Options: DENY',
         '/embed/ パスのみ例外設定済み。URLが正しいか確認'],
        ['ブラウザ投稿が失敗', 'セッション期限切れ',
         'サーバーで再ログインしてセッション更新'],
        ['X API投稿が 429 エラー', '月500投稿の上限到達',
         '翌月まで待つか、ブラウザ投稿に切り替え'],
        ['文字数超過の警告', 'プラットフォーム制限超過',
         '編集画面で文字数カウンターを確認しながら修正'],
        ['サイドバーに機能が見えない', '機能表示トグルがOFF',
         'サイト設定で対象機能のトグルをON。スーパーユーザーは常に全表示'],
    ]
    t = Table(ts_data, colWidths=[38 * mm, 45 * mm, 85 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(t)
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph('APIキー・トークンの管理', S_H3))
    story.append(Paragraph(
        '全てのAPIキー・トークンは暗号化して保存されます（EncryptedCharField）。'
        '.env ファイルに平文で保存しないでください。', S_BODY))
    story.append(Spacer(1, 3 * mm))

    key_data = [
        ['キー/トークン', '保存場所', '更新方法'],
        ['GEMINI_API_KEY', '.env ファイル', 'Google AI Studio で再発行'],
        ['X OAuth トークン', 'SocialAccount (暗号化DB)', '管理画面で再連携'],
        ['embed_api_key', 'Store モデル (DB)', '管理画面 → 「APIキー生成」アクション'],
        ['ブラウザセッション', 'storage_state.json', 'サーバーで再ログイン'],
    ]
    t = Table(key_data, colWidths=[38 * mm, 50 * mm, 80 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, -1), 'HeiseiKakuGo-W5'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db')),
        ('BACKGROUND', (0, 1), (-1, -1), BG_BLUE),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # フッター
    story.append(HRFlowable(width='100%', color=GRAY, thickness=0.5))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        f'Timebaibai SNS自動投稿 &amp; WordPress埋め込みガイド — {today}',
        ParagraphStyle('Footer', fontName='HeiseiKakuGo-W5', fontSize=8,
                       textColor=GRAY, alignment=TA_CENTER)))
    story.append(Paragraph(
        'https://timebaibai.com',
        ParagraphStyle('FooterURL', fontName='HeiseiKakuGo-W5', fontSize=8,
                       textColor=LIGHT_BLUE, alignment=TA_CENTER)))

    doc.build(story)
    print(f'PDF generated: {output_path}')
    return output_path


if __name__ == '__main__':
    build_pdf()
