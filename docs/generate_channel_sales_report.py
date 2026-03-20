#!/usr/bin/env python3
"""
チャネル別売上分析機能 — 実装報告PDF生成スクリプト
"""
from fpdf import FPDF, XPos, YPos
import os
from datetime import datetime

FONT_PATH = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
FONT_BOLD_PATH = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'チャネル別売上分析_実装報告.pdf')

# Colors
BLUE = (59, 130, 246)
GREEN = (16, 185, 129)
AMBER = (245, 158, 11)
PURPLE = (139, 92, 246)
DARK = (31, 41, 55)
GRAY = (107, 114, 128)
LIGHT_BG = (249, 250, 251)
WHITE = (255, 255, 255)
BORDER = (229, 231, 235)


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_font('Gothic', '', FONT_PATH)
        self.add_font('GothicB', '', FONT_BOLD_PATH)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font('Gothic', size=8)
        self.set_text_color(*GRAY)
        self.cell(0, 6, 'チャネル別売上分析機能 実装報告', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*BORDER)
        self.line(10, 12, 200, 12)
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font('Gothic', size=8)
        self.set_text_color(*GRAY)
        self.cell(0, 10, f'{self.page_no()}', align='C')

    def title_page(self):
        self.add_page()
        self.ln(50)
        # Title
        self.set_font('GothicB', size=28)
        self.set_text_color(*DARK)
        self.cell(0, 16, 'チャネル別売上分析機能', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        self.set_font('GothicB', size=20)
        self.set_text_color(*BLUE)
        self.cell(0, 12, '実装報告書', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(20)

        # Subtitle info
        self.set_font('Gothic', size=12)
        self.set_text_color(*GRAY)
        today = datetime.now().strftime('%Y年%m月%d日')
        self.cell(0, 8, f'報告日: {today}', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 8, 'プロジェクト: NewFUHI (TimeBaiBai)', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 8, '対象: 売上ダッシュボード', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Channel color legend
        self.ln(30)
        self.set_font('GothicB', size=11)
        self.set_text_color(*DARK)
        self.cell(0, 8, '対応チャネル', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        channels = [
            ('EC', BLUE), ('POS', GREEN),
            ('Table', AMBER), ('Reservation', PURPLE),
        ]
        box_w = 35
        start_x = (210 - box_w * len(channels) - 8 * (len(channels) - 1)) / 2
        y = self.get_y()
        for i, (label, color) in enumerate(channels):
            x = start_x + i * (box_w + 8)
            self.set_fill_color(*color)
            self.set_xy(x, y)
            self.set_font('GothicB', size=11)
            self.set_text_color(*WHITE)
            self.cell(box_w, 12, label, fill=True, align='C')

    def section_title(self, text):
        self.ln(6)
        self.set_font('GothicB', size=16)
        self.set_text_color(*BLUE)
        self.cell(0, 10, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*BLUE)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_title(self, text):
        self.ln(3)
        self.set_font('GothicB', size=13)
        self.set_text_color(*DARK)
        self.cell(0, 8, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def body_text(self, text):
        self.set_font('Gothic', size=10)
        self.set_text_color(*DARK)
        self.multi_cell(0, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def bullet(self, text, indent=15):
        self.set_font('Gothic', size=10)
        self.set_text_color(*DARK)
        self.set_x(self.l_margin + indent)
        w = self.w - self.l_margin - self.r_margin - indent
        self.multi_cell(w, 6, f'  {text}', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def info_box(self, text, color=BLUE):
        self.ln(2)
        self.set_fill_color(color[0], color[1], color[2])
        self.set_draw_color(color[0], color[1], color[2])
        y = self.get_y()
        # Left accent bar
        self.rect(10, y, 3, 20, 'F')
        self.set_fill_color(color[0] // 4 + 191, color[1] // 4 + 191, color[2] // 4 + 191)
        self.rect(13, y, 187, 20, 'F')
        self.set_xy(18, y + 3)
        self.set_font('Gothic', size=10)
        self.set_text_color(*DARK)
        self.multi_cell(175, 6, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + 22)

    def table_row(self, cols, widths, bold=False, fill=False):
        font = 'GothicB' if bold else 'Gothic'
        self.set_font(font, size=9)
        if fill:
            self.set_fill_color(*LIGHT_BG)
        self.set_text_color(*DARK)
        self.set_draw_color(*BORDER)
        for i, (col, w) in enumerate(zip(cols, widths)):
            self.cell(w, 8, col, border=1, fill=fill, align='C' if i == 0 else 'L')
        self.ln()


def build_report():
    pdf = ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # ===== Page 1: Title =====
    pdf.title_page()

    # ===== Page 2: Overview =====
    pdf.add_page()
    pdf.section_title('1. 概要')
    pdf.body_text(
        '売上ダッシュボードに「チャネル別売上」分析機能を追加しました。\n'
        'EC / POS / テーブル注文 / 予約の4チャネルについて、日次・週次・月次の売上推移を'
        '積み上げ棒グラフで可視化します。\n\n'
        'SiteSettings の機能トグルと連動し、無効化されたチャネルは自動的に非表示になります。'
    )

    pdf.info_box(
        '目的: チャネル別売上の内訳を可視化し、機能停止中のチャネルは非表示にする。'
    )

    pdf.section_title('2. 変更ファイル一覧')
    widths = [10, 100, 80]
    pdf.table_row(['#', 'ファイル', '操作'], widths, bold=True, fill=True)
    files = [
        ('1', 'booking/views_restaurant_dashboard.py', '修正 (APIビュー追加)'),
        ('2', 'booking/api_urls.py', '修正 (エンドポイント登録)'),
        ('3', 'templates/.../restaurant_dashboard.html', '修正 (サブタブ + JS追加)'),
        ('4', 'booking/tests/test_channel_sales_api.py', '新規 (テスト11件)'),
    ]
    for f in files:
        pdf.table_row(list(f), widths)

    # ===== Page 3: API Details =====
    pdf.add_page()
    pdf.section_title('3. API仕様')

    pdf.sub_title('3.1 エンドポイント')
    pdf.body_text('GET /api/dashboard/channel-sales/?period=daily|weekly|monthly')

    pdf.sub_title('3.2 レスポンス構造')
    pdf.body_text(
        '{\n'
        '  "channels": ["pos", "table", "ec", "reservation"],\n'
        '  "trend": [\n'
        '    {"date": "2026-03-19", "channel": "pos", "total": 15000},\n'
        '    {"date": "2026-03-19", "channel": "ec", "total": 8000}\n'
        '  ],\n'
        '  "channel_labels": {\n'
        '    "ec": "ECショップ", "pos": "POS",\n'
        '    "table": "テーブル注文", "reservation": "予約"\n'
        '  }\n'
        '}'
    )

    pdf.sub_title('3.3 チャネルフィルタロジック')
    pdf.bullet('SiteSettings.show_admin_pos = True  ->  pos, table を含む')
    pdf.bullet('SiteSettings.show_admin_ec_shop = True  ->  ec を含む')
    pdf.bullet('SiteSettings.show_admin_reservation = True  ->  reservation を含む')
    pdf.bullet('全て False の場合 -> channels=[], trend=[] (空結果)')

    pdf.sub_title('3.4 認証・スコープ')
    pdf.bullet('未認証 -> 403 Forbidden')
    pdf.bullet('superuser -> 全店舗集計')
    pdf.bullet('スタッフ -> 自店舗のみ (store scope)')

    # ===== Page 4: Frontend =====
    pdf.add_page()
    pdf.section_title('4. フロントエンド実装')

    pdf.sub_title('4.1 UI配置')
    pdf.body_text(
        '売上タブのサブタブバーに「チャネル別売上」ボタンを追加。\n'
        'クリックで /api/dashboard/channel-sales/ を fetch し、Chart.js で積み上げ棒グラフを描画します。\n'
        '期間セレクト (日別/週別/月別) で切り替え可能。'
    )

    pdf.sub_title('4.2 チャネル別カラー')
    channels_detail = [
        ('EC (ECショップ)', '#3B82F6', BLUE),
        ('POS', '#10B981', GREEN),
        ('テーブル注文', '#F59E0B', AMBER),
        ('予約', '#8B5CF6', PURPLE),
    ]
    y = pdf.get_y() + 2
    for label, hex_code, rgb in channels_detail:
        pdf.set_fill_color(*rgb)
        pdf.set_xy(15, y)
        pdf.rect(15, y + 1, 10, 6, 'F')
        pdf.set_xy(28, y)
        pdf.set_font('Gothic', size=10)
        pdf.set_text_color(*DARK)
        pdf.cell(80, 8, f'{label}  ({hex_code})')
        y += 10
    pdf.set_y(y + 4)

    pdf.sub_title('4.3 グラフ仕様')
    pdf.bullet('Chart.js v4 積み上げ棒グラフ (stacked bar)')
    pdf.bullet('X軸: 日付 (maxTicksLimit: 12)')
    pdf.bullet('Y軸: 売上 (円) ロケール表示')
    pdf.bullet('ツールチップ: チャネル名 + 金額')
    pdf.bullet('レスポンシブ対応 (maintainAspectRatio: false)')

    # ===== Page 5: Test Results =====
    pdf.add_page()
    pdf.section_title('5. テスト結果')

    pdf.info_box('11件全テスト通過 (0.300秒)  — OK', GREEN)
    pdf.ln(4)

    widths_test = [10, 95, 60, 25]
    pdf.table_row(['#', 'テストケース', 'クラス名', '結果'], widths_test, bold=True, fill=True)
    tests = [
        ('1', '未認証 -> 403', 'TestChannelSalesAuth', 'OK'),
        ('2', '認証済み -> 200 + 構造確認', 'TestChannelSalesBasic', 'OK'),
        ('3', 'EC無効 -> ec除外', 'TestChannelSalesECDisabled', 'OK'),
        ('4', 'POS無効 -> pos,table除外', 'TestChannelSalesPOSDisabled', 'OK'),
        ('5', '予約無効 -> reservation除外', 'TestChannelSalesReservation...', 'OK'),
        ('6', 'period=daily', 'TestChannelSalesPeriodDaily', 'OK'),
        ('7', 'period=weekly', 'TestChannelSalesPeriodWeekly', 'OK'),
        ('8', 'period=monthly', 'TestChannelSalesPeriodMonthly', 'OK'),
        ('9', 'チャネル別金額が正確', 'TestChannelSalesAmounts', 'OK'),
        ('10', 'スタッフ自店舗のみ', 'TestChannelSalesStoreScope', 'OK'),
        ('11', '全チャネル無効 -> 空結果', 'TestChannelSalesAllDisabled', 'OK'),
    ]
    for t in tests:
        pdf.table_row(list(t), widths_test)

    # ===== Page 6: Architecture =====
    pdf.add_page()
    pdf.section_title('6. アーキテクチャ')

    pdf.sub_title('6.1 データフロー')
    pdf.body_text(
        'ブラウザ (Chart.js)\n'
        '    |  fetch GET /api/dashboard/channel-sales/?period=daily\n'
        '    v\n'
        'ChannelSalesAPIView\n'
        '    |  認証チェック + store scope 決定\n'
        '    |  SiteSettings.load() -> 有効チャネル判定\n'
        '    v\n'
        'OrderItem.objects.filter(...)\n'
        '    .annotate(date=TruncDate/Week/Month)\n'
        '    .values("date", "order__channel")\n'
        '    .annotate(total=Sum(qty * unit_price))\n'
        '    |  単一クエリで全チャネル集計\n'
        '    v\n'
        'JSON Response -> Chart.js 積み上げ棒グラフ'
    )

    pdf.sub_title('6.2 既存パターンとの整合性')
    pdf.bullet('SalesStatsAPIView.TRUNC_MAP を共有 (DRY)')
    pdf.bullet('_get_store_scope と同等のスコープロジック')
    pdf.bullet('SiteSettings.load() による機能トグル連動')
    pdf.bullet('既存サブタブ UI パターンを踏襲')

    pdf.sub_title('6.3 パフォーマンス考慮')
    pdf.bullet('単一SQLクエリで全チャネル・全日付を集計')
    pdf.bullet('order__channel に db_index=True 済み')
    pdf.bullet('遅延ロード (サブタブ選択時のみ fetch)')

    # ===== Page 7: Conclusion =====
    pdf.add_page()
    pdf.section_title('7. まとめ')
    pdf.body_text(
        '本機能により、管理者は売上ダッシュボード内で EC / POS / テーブル注文 / 予約 の\n'
        'チャネル別売上推移を一目で把握できるようになりました。\n\n'
        'SiteSettings のトグルと連動しているため、利用していないチャネルは自動的に非表示となり、\n'
        '各店舗の業態に合わせた柔軟な表示が可能です。'
    )

    pdf.ln(6)
    pdf.sub_title('変更量サマリー')
    widths_sum = [95, 95]
    pdf.table_row(['項目', '内容'], widths_sum, bold=True, fill=True)
    summary = [
        ('変更ファイル数', '4ファイル (3修正 + 1新規)'),
        ('新規APIエンドポイント', '1件'),
        ('テスト件数', '11件 (全通過)'),
        ('テスト実行時間', '0.300秒'),
        ('グラフ種別', 'Chart.js 積み上げ棒グラフ'),
        ('対応チャネル', 'EC / POS / テーブル / 予約'),
        ('期間切替', '日別 / 週別 / 月別'),
    ]
    for s in summary:
        pdf.table_row(list(s), widths_sum)

    pdf.ln(10)
    pdf.info_box('次のステップ: ローカルダッシュボードで売上タブ -> チャネル別売上 サブタブを確認してください。')

    # Output
    pdf.output(OUTPUT_FILE)
    print(f'PDF generated: {OUTPUT_FILE}')


if __name__ == '__main__':
    build_report()
