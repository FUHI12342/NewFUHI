#!/usr/bin/env python3
"""Timebaibai SNS自動投稿+WordPress埋め込み 機能ガイド PDF (fpdf2)"""
import datetime
from fpdf import FPDF


class PDF(FPDF):
    def __init__(self):
        super().__init__()
        # 日本語フォント
        self.add_font('noto', '', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', uni=True)
        self.add_font('noto', 'B', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', uni=True)

    def header(self):
        if self.page_no() > 1:
            self.set_font('noto', '', 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 8, 'Timebaibai 新機能ガイド', align='L')
            self.cell(0, 8, f'p.{self.page_no()}', align='R', new_x='LMARGIN', new_y='NEXT')
            self.line(10, 16, 200, 16)
            self.ln(4)

    def h1(self, text):
        self.set_font('noto', 'B', 18)
        self.set_text_color(30, 64, 175)
        self.cell(0, 12, text, new_x='LMARGIN', new_y='NEXT')
        self.set_draw_color(30, 64, 175)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def h2(self, text):
        self.set_font('noto', 'B', 14)
        self.set_text_color(30, 58, 95)
        self.set_draw_color(59, 130, 246)
        self.set_fill_color(59, 130, 246)
        self.rect(10, self.get_y(), 3, 8, 'F')
        self.cell(6, 8)
        self.cell(0, 8, text, new_x='LMARGIN', new_y='NEXT')
        self.ln(3)

    def h3(self, text):
        self.set_font('noto', 'B', 11)
        self.set_text_color(55, 65, 81)
        self.cell(0, 8, text, new_x='LMARGIN', new_y='NEXT')
        self.ln(2)

    def body_text(self, text):
        self.set_font('noto', '', 10)
        self.set_text_color(26, 26, 26)
        self.multi_cell(0, 6, text)
        self.ln(3)

    def note_box(self, text, bg=(254, 243, 199), border=(245, 158, 11)):
        self.set_fill_color(*bg)
        self.set_draw_color(*border)
        x, y = self.get_x(), self.get_y()
        self.rect(10, y, 190, 2, 'F')
        self.rect(10, y, 3, 20, 'F')
        self.set_xy(16, y + 3)
        self.set_font('noto', '', 9)
        self.set_text_color(26, 26, 26)
        self.multi_cell(180, 5, text)
        self.ln(5)

    def info_box(self, text):
        self.note_box(text, bg=(239, 246, 255), border=(59, 130, 246))

    def success_box(self, text):
        self.note_box(text, bg=(236, 253, 245), border=(16, 185, 129))

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)
        self.set_font('noto', 'B', 9)
        self.set_fill_color(239, 246, 255)
        self.set_text_color(30, 58, 95)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 8, h, border=1, fill=True, align='C')
        self.ln()
        self.set_font('noto', '', 9)
        self.set_text_color(26, 26, 26)
        for row_idx, row in enumerate(rows):
            if row_idx % 2 == 1:
                self.set_fill_color(249, 250, 251)
                fill = True
            else:
                self.set_fill_color(255, 255, 255)
                fill = True
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 7, str(cell), border=1, fill=fill)
            self.ln()
        self.ln(4)

    def flow_step(self, num, text):
        self.set_font('noto', 'B', 10)
        self.set_fill_color(59, 130, 246)
        self.set_text_color(255, 255, 255)
        x = self.get_x()
        self.cell(8, 7, str(num), fill=True, align='C')
        self.set_text_color(26, 26, 26)
        self.set_font('noto', '', 10)
        self.cell(2, 7)
        self.multi_cell(170, 7, text)
        self.ln(1)

    def code_block(self, text):
        self.set_fill_color(31, 41, 55)
        self.set_text_color(229, 231, 235)
        self.set_font('Courier', '', 8)
        y = self.get_y()
        lines = text.split('\n')
        h = len(lines) * 5 + 8
        self.rect(10, y, 190, h, 'F')
        self.set_xy(14, y + 4)
        for line in lines:
            self.cell(0, 5, line, new_x='LMARGIN', new_y='NEXT')
            self.set_x(14)
        self.set_text_color(26, 26, 26)
        self.ln(6)


def main():
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # === 表紙 ===
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font('noto', 'B', 32)
    pdf.set_text_color(30, 64, 175)
    pdf.cell(0, 15, 'Timebaibai', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('noto', 'B', 20)
    pdf.cell(0, 12, '新機能ガイド', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(5)
    pdf.set_font('noto', '', 13)
    pdf.set_text_color(107, 114, 128)
    pdf.cell(0, 8, 'SNS自動投稿 + AI生成 + WordPress埋め込み', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, '占いサロンチャンス 管理者向け', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(20)
    pdf.set_font('noto', '', 11)
    pdf.set_text_color(156, 163, 175)
    today = datetime.date.today().strftime('%Y年%m月%d日')
    pdf.cell(0, 8, today, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.cell(0, 8, 'https://timebaibai.com', align='C', new_x='LMARGIN', new_y='NEXT')

    # === 目次 ===
    pdf.add_page()
    pdf.h1('目次')
    toc = [
        '1. 機能概要',
        '2. RAGナレッジ管理',
        '3. AI下書き生成 + LLM Judge評価',
        '4. 投稿フロー（即時・予約）',
        '5. コスト試算',
        '6. WordPress iframe埋め込み',
        '7. 初期セットアップ手順',
    ]
    for item in toc:
        pdf.set_font('noto', '', 12)
        pdf.set_text_color(30, 64, 175)
        pdf.cell(0, 9, item, new_x='LMARGIN', new_y='NEXT')

    # === 1. 機能概要 ===
    pdf.add_page()
    pdf.h1('1. 機能概要')
    pdf.h2('3つの主要機能')
    pdf.table(
        ['機能', '概要', '技術'],
        [
            ['RAGナレッジ', 'キャスト・店舗情報をDBに蓄積、AI精度を担保', 'KnowledgeEntry'],
            ['AI下書き+LLM Judge', 'Gemini APIで投稿文自動生成、品質自動評価', 'Gemini 2.0 Flash'],
            ['WordPress埋め込み', '予約/シフトをiframeで外部サイトに埋め込み', 'APIキー認証+CSP'],
        ],
        [45, 90, 55],
    )
    pdf.h2('システム全体図')
    pdf.body_text(
        'RAG Knowledge (ナレッジDB)\n'
        '    ↓\n'
        'Gemini API (AI生成)\n'
        '    ↓\n'
        'DraftPost (下書き) → LLM Judge (品質評価)\n'
        '    ↓\n'
        '下書き管理UI (編集・承認・投稿)\n'
        '    ↓\n'
        'X API / Instagram Browser / GBP Browser'
    )

    # === 2. RAG ===
    pdf.add_page()
    pdf.h1('2. RAGナレッジ管理')
    pdf.h2('目的')
    pdf.body_text(
        'AIが正確な投稿文を生成するための「事実データベース」です。\n'
        'キャスト名、得意占術、店舗情報などを登録しておくと、AI生成時に自動参照されます。'
    )
    pdf.h2('管理画面の操作')
    pdf.body_text('管理画面 → SNS自動投稿 → SNSナレッジ')
    pdf.table(
        ['カテゴリ', 'タイトル例', '内容例'],
        [
            ['キャストプロフィール', '星野ルナのプロフィール', 'タロット・西洋占星術が得意...'],
            ['店舗情報', '店舗基本情報', '高円寺駅徒歩3分、営業11-23時'],
            ['サービス情報', '占いメニュー', 'タロット、手相、霊視 各30-60分'],
            ['キャンペーン', '春の特別鑑定', '4月限定 初回30%OFF'],
        ],
        [50, 55, 85],
    )
    pdf.h2('カテゴリ一覧')
    pdf.table(
        ['カテゴリ', '用途', '例'],
        [
            ['キャストプロフィール', '占い師の情報', '名前、得意占術、紹介文'],
            ['店舗情報', '基本情報', '住所、営業時間、最寄駅'],
            ['サービス情報', 'メニュー詳細', '占術一覧、料金、所要時間'],
            ['キャンペーン', '期間限定情報', '初回割引、季節イベント'],
            ['カスタム', '自由記入', '注意事項、特記事項'],
        ],
        [55, 55, 80],
    )

    # === 3. AI下書き + LLM Judge ===
    pdf.add_page()
    pdf.h1('3. AI下書き生成 + LLM Judge評価')
    pdf.h2('下書き管理UI')
    pdf.body_text('管理画面 → サイドバー「SNS下書き管理」または /admin/social/drafts/')
    pdf.ln(2)
    pdf.h3('下書きカード表示例')
    pdf.table(
        ['ステータス', '品質スコア', 'Platform', '内容（抜粋）'],
        [
            ['生成済み', '0.70', 'X, Instagram', '占いサロンチャンス高円寺店より。本日は星野ルナ先生...'],
            ['予約済み (3/31 10:00)', '0.70', 'X', '明日の占いサロンチャンス高円寺店は朝霧ヒカル先生...'],
            ['投稿済み', '0.85', 'X', '占いサロンチャンス高円寺店、本日も元気に営業中！...'],
            ['生成済み (要改善)', '0.60', 'X, Insta, GBP', '今日も占い師が出勤してます！→店名なし'],
        ],
        [40, 25, 35, 90],
    )

    pdf.h2('AI生成フロー')
    pdf.flow_step(1, '「新規生成」ボタン → 店舗・対象日・プラットフォームを選択')
    pdf.flow_step(2, 'RAGコンテキスト自動構築: ナレッジDB + 当日出勤キャスト情報')
    pdf.flow_step(3, 'Gemini 2.0 Flash が投稿文を生成（280加重文字以内、絵文字付き）')
    pdf.flow_step(4, 'LLM Judge が自動評価（ルールベース + AI評価の複合スコア）')
    pdf.flow_step(5, '下書き一覧に「生成済み」ステータスで表示')

    pdf.h2('LLM Judge 評価基準')
    pdf.table(
        ['チェック項目', '方式', '配点', '内容'],
        [
            ['店舗名チェック', 'ルール（即時）', '-', '店舗名が含まれているか'],
            ['禁止ワード', 'ルール（即時）', '-', '不適切な表現がないか'],
            ['文字数', 'ルール（即時）', '-', '加重文字数280以内（X用）'],
            ['事実正確性', 'LLM Judge（AI）', '30%', 'キャスト名・占術が正確か'],
            ['文章品質', 'LLM Judge（AI）', '30%', '自然で読みやすいか'],
            ['集客効果', 'LLM Judge（AI）', '20%', '来店意欲を喚起できるか'],
            ['Platform適合', 'LLM Judge（AI）', '20%', 'X/Insta/GBPの特性に合うか'],
        ],
        [40, 40, 20, 90],
    )

    pdf.h2('品質スコアの目安')
    pdf.table(
        ['スコア', '評価', '推奨アクション'],
        [
            ['0.80〜1.00', '高品質', 'そのまま投稿OK'],
            ['0.60〜0.79', '標準', '確認後投稿、必要に応じ微修正'],
            ['0.00〜0.59', '要改善', '手動編集 or 再生成を推奨'],
        ],
        [40, 40, 110],
    )

    # === 4. 投稿フロー ===
    pdf.add_page()
    pdf.h1('4. 投稿フロー')
    pdf.h2('即時投稿')
    pdf.flow_step(1, '下書き一覧で「投稿」ボタンをクリック')
    pdf.flow_step(2, 'プラットフォーム確認 → 「投稿する」で実行')
    pdf.flow_step(3, 'X: API経由 / Instagram・GBP: ブラウザ自動投稿')
    pdf.flow_step(4, 'ステータスが「投稿済み」に変更')

    pdf.h2('予約投稿')
    pdf.flow_step(1, '下書き一覧で「予約投稿」ボタンをクリック')
    pdf.flow_step(2, '投稿日時をカレンダーで指定')
    pdf.flow_step(3, 'ステータスが「予約済み」に変更')
    pdf.flow_step(4, 'Celery Beat が5分ごとにチェック → 時刻到達で自動投稿')

    pdf.h2('自動生成スケジュール')
    pdf.info_box('毎朝08:00に Celery Beat が全店舗の下書きを自動AI生成します。\n管理者は出勤後にチェック → 承認 → 投稿/予約投稿。')

    pdf.h2('プラットフォーム別投稿方式')
    pdf.table(
        ['Platform', '方式', '認証', '制限'],
        [
            ['X (Twitter)', 'API v2 (OAuth 2.0)', '管理画面でOAuth連携', '月500件 (Free)'],
            ['Instagram', 'ブラウザ自動投稿', '初回手動ログイン', '1日1〜2件推奨'],
            ['Google Business', 'ブラウザ自動投稿', '初回手動ログイン', '1日1件推奨'],
        ],
        [35, 50, 50, 55],
    )

    # === 5. コスト ===
    pdf.add_page()
    pdf.h1('5. コスト試算')
    pdf.h2('月間コスト概算（1店舗・1日1投稿）')
    pdf.table(
        ['項目', '単価', '月間使用量', '月額'],
        [
            ['Gemini 2.0 Flash (生成)', '無料枠:100万トークン/日', '~30回×1,000tok', '¥0'],
            ['Gemini 2.0 Flash (Judge)', '同上', '~30回×500tok', '¥0'],
            ['X API Free Tier', '無料 (月500件)', '~30件', '¥0'],
            ['Playwright (OSS)', '無料', '-', '¥0'],
            ['EC2 t3.micro (既存)', '~$8.5/月', '常時稼働', '¥1,300 (既存)'],
        ],
        [50, 55, 40, 45],
    )
    pdf.success_box('結論: 現在の利用規模では追加コストゼロで運用できます。\nGemini API無料枠、X API Free (月500件) の範囲内です。')

    pdf.h2('スケールアップ時')
    pdf.table(
        ['規模', 'Gemini API', 'X API', '月額追加'],
        [
            ['1店舗×1日1投稿', '無料枠内', 'Free (500/月)', '¥0'],
            ['5店舗×1日1投稿', '無料枠内', 'Free (500/月)', '¥0'],
            ['10店舗×1日2投稿', 'Pay-as-you-go', 'Basic ($100/月)', '~¥15,000'],
        ],
        [50, 50, 50, 40],
    )

    # === 6. WordPress ===
    pdf.add_page()
    pdf.h1('6. WordPress iframe埋め込み')
    pdf.h2('概要')
    pdf.body_text(
        'Timebaibai の予約カレンダーやシフト表示を、WordPressサイトにiframeで埋め込めます。\n'
        'timebaibai.com 本体には一切影響ありません。'
    )

    pdf.h2('Step 1: Timebaibai管理画面で有効化')
    pdf.flow_step(1, '管理画面 → メインサイト設定 → 「外部埋め込みを有効化」をON')
    pdf.flow_step(2, '管理画面 → 店舗一覧 → 対象店舗を選択')
    pdf.flow_step(3, 'アクション「埋め込みAPIキーを生成」を実行 → 64文字のキー発行')
    pdf.flow_step(4, '（推奨）「埋め込み許可ドメイン」にWPのドメインを入力')

    pdf.h2('Step 2: WordPressにショートコード追加')
    pdf.body_text('テーマの functions.php に docs/wordpress/newfuhi-embed.php の内容を追加')

    pdf.h2('Step 3: ページにショートコードを記述')
    pdf.body_text(
        '[newfuhi_booking store_id="1" api_key="YOUR_API_KEY"]\n'
        '[newfuhi_shift store_id="1" api_key="YOUR_API_KEY"]'
    )

    pdf.h2('HTML直接埋め込み（WordPress不使用の場合）')
    pdf.body_text(
        '<iframe\n'
        '  src="https://timebaibai.com/embed/booking/1/?api_key=KEY"\n'
        '  width="100%" height="600"\n'
        '  style="border:none; max-width:100%;"\n'
        '  loading="lazy"\n'
        '></iframe>'
    )

    pdf.h2('埋め込みURL一覧')
    pdf.table(
        ['URL', '表示内容', '用途'],
        [
            ['/embed/booking/<store_id>/', '予約カレンダー', '顧客が予約スロットを選択'],
            ['/embed/shift/<store_id>/', '本日のシフト', '出勤キャスト一覧を公開'],
        ],
        [70, 50, 70],
    )

    pdf.h2('セキュリティ')
    pdf.table(
        ['脅威', '対策'],
        [
            ['APIキーなし/不正', '403 Forbidden を返却'],
            ['埋め込み無効時', '404 Not Found を返却'],
            ['不正ドメインからの埋め込み', 'CSP frame-ancestors ヘッダーで制限'],
            ['他ページのiframe表示', 'X-Frame-Options: DENY を維持'],
        ],
        [70, 120],
    )

    # === 7. セットアップ ===
    pdf.add_page()
    pdf.h1('7. 初期セットアップ手順')
    pdf.h2('SNS自動投稿の初期設定')
    pdf.flow_step(1, 'Gemini APIキー設定: aistudio.google.com でキー取得 → EC2の.envに追加')
    pdf.flow_step(2, 'ナレッジ登録: 管理画面→SNSナレッジ→キャスト/店舗/サービス情報を登録')
    pdf.flow_step(3, '下書き生成テスト: SNS下書き管理→新規生成→AI生成を確認')
    pdf.flow_step(4, 'X OAuth連携（任意）: SNSアカウント→X連携→OAuth認証フロー実行')
    pdf.flow_step(5, '投稿テスト: 下書き→投稿ボタン→Xに投稿されることを確認')

    pdf.h2('日常運用フロー')
    pdf.info_box('毎朝の流れ（5分で完了）:\n08:00 Celeryが自動で下書き生成 → 管理者がチェック → 承認して投稿/予約投稿')

    pdf.h2('注意事項')
    pdf.note_box(
        '- Gemini API無料枠: 15リクエスト/分、100万トークン/日\n'
        '- X API Free: 月500件まで（超過時は翌月リセット）\n'
        '- Instagram/GBP ブラウザ投稿: 1日1〜2件推奨（BAN防止）\n'
        '- ブラウザ投稿を使う場合、EC2にPlaywrightインストールが必要'
    )

    # 出力
    output = '/home/ubuntu/NewFUHI/docs/timebaibai_feature_guide.pdf'
    pdf.output(output)
    print(f'PDF generated: {output}')


if __name__ == '__main__':
    main()
