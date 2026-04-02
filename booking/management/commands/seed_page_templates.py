"""Seed 5 system page templates for GrapesJS page builder."""
from django.core.management.base import BaseCommand

from booking.models import PageTemplate


TEMPLATES = [
    {
        'name': 'サロン紹介LP',
        'description': 'サロンの魅力を伝えるフルワイドのランディングページ。ヒーロー画像・コンセプト・アクセス情報を配置。',
        'category': 'salon',
        'html_content': '''
<section style="position:relative;min-height:70vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#8c876c 0%,#b8a88a 100%);color:#fff;text-align:center;">
  <div style="max-width:700px;padding:40px 20px;">
    <h1 style="font-size:2.5rem;font-weight:700;margin-bottom:16px;">あなただけの特別な時間</h1>
    <p style="font-size:1.1rem;opacity:0.9;margin-bottom:32px;">心と体を癒す、上質なサロン体験をお届けします</p>
    <a href="#concept" style="display:inline-block;background:#fff;color:#8c876c;padding:14px 40px;border-radius:30px;font-weight:600;text-decoration:none;">詳しく見る</a>
  </div>
</section>

<section id="concept" style="padding:80px 20px;max-width:900px;margin:0 auto;text-align:center;">
  <h2 style="font-size:1.8rem;font-weight:700;color:#8c876c;margin-bottom:16px;">コンセプト</h2>
  <div style="width:60px;height:3px;background:#8c876c;margin:0 auto 32px;"></div>
  <p style="font-size:1rem;line-height:2;color:#444;">
    当サロンは、お客様一人ひとりに寄り添った丁寧なサービスを心がけています。<br>
    落ち着いた空間で、日常の疲れを忘れるひとときをお過ごしください。
  </p>
</section>

<section style="padding:60px 20px;background:#f8f6f2;">
  <div style="max-width:900px;margin:0 auto;text-align:center;">
    <h2 style="font-size:1.8rem;font-weight:700;color:#8c876c;margin-bottom:40px;">メニュー</h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:24px;">
      <div style="background:#fff;padding:32px 24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <h3 style="font-size:1.2rem;font-weight:600;color:#8c876c;margin-bottom:8px;">ベーシックコース</h3>
        <p style="color:#666;margin-bottom:12px;">初めての方にもおすすめの基本メニュー</p>
        <p style="font-size:1.5rem;font-weight:700;color:#8c876c;">¥5,000〜</p>
      </div>
      <div style="background:#fff;padding:32px 24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <h3 style="font-size:1.2rem;font-weight:600;color:#8c876c;margin-bottom:8px;">プレミアムコース</h3>
        <p style="color:#666;margin-bottom:12px;">贅沢な時間をお過ごしいただけます</p>
        <p style="font-size:1.5rem;font-weight:700;color:#8c876c;">¥10,000〜</p>
      </div>
      <div style="background:#fff;padding:32px 24px;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <h3 style="font-size:1.2rem;font-weight:600;color:#8c876c;margin-bottom:8px;">スペシャルコース</h3>
        <p style="color:#666;margin-bottom:12px;">特別な日のための最上級メニュー</p>
        <p style="font-size:1.5rem;font-weight:700;color:#8c876c;">¥20,000〜</p>
      </div>
    </div>
  </div>
</section>

<section style="padding:60px 20px;text-align:center;">
  <h2 style="font-size:1.8rem;font-weight:700;color:#8c876c;margin-bottom:32px;">ご予約はこちら</h2>
  <a href="/" style="display:inline-block;background:#8c876c;color:#fff;padding:16px 48px;border-radius:30px;font-size:1.1rem;font-weight:600;text-decoration:none;">予約ページへ</a>
</section>
''',
        'css_content': '''
body { font-family: "Noto Sans JP", "Hiragino Sans", sans-serif; }
section { scroll-margin-top: 60px; }
a:hover { opacity: 0.85; }
''',
        'grapesjs_data': {},
    },
    {
        'name': 'キャンペーンページ',
        'description': '期間限定キャンペーンの告知用。目立つカウントダウン風デザインと特典情報。',
        'category': 'general',
        'html_content': '''
<section style="background:linear-gradient(135deg,#e74c3c 0%,#c0392b 100%);color:#fff;padding:60px 20px;text-align:center;">
  <div style="max-width:700px;margin:0 auto;">
    <p style="font-size:0.9rem;letter-spacing:4px;margin-bottom:8px;">SPECIAL CAMPAIGN</p>
    <h1 style="font-size:2.2rem;font-weight:800;margin-bottom:16px;">春の特別キャンペーン</h1>
    <p style="font-size:1.1rem;opacity:0.9;">期間限定 ─ 2026年4月1日〜4月30日</p>
  </div>
</section>

<section style="padding:60px 20px;max-width:800px;margin:0 auto;">
  <div style="background:#fff3f3;border:2px solid #e74c3c;border-radius:16px;padding:40px;text-align:center;margin-bottom:40px;">
    <p style="color:#e74c3c;font-size:1rem;font-weight:600;margin-bottom:8px;">今だけの特別価格</p>
    <p style="font-size:3rem;font-weight:800;color:#e74c3c;margin-bottom:8px;">30<span style="font-size:1.5rem;">%</span> OFF</p>
    <p style="color:#666;">全メニュー対象・ご新規様限定</p>
  </div>

  <h2 style="font-size:1.5rem;font-weight:700;text-align:center;margin-bottom:32px;color:#333;">キャンペーン特典</h2>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:20px;">
    <div style="background:#fafafa;padding:24px;border-radius:12px;text-align:center;">
      <p style="font-size:2rem;margin-bottom:8px;">🎁</p>
      <h3 style="font-weight:600;margin-bottom:8px;">特典1</h3>
      <p style="color:#666;font-size:0.9rem;">初回施術30%OFF</p>
    </div>
    <div style="background:#fafafa;padding:24px;border-radius:12px;text-align:center;">
      <p style="font-size:2rem;margin-bottom:8px;">💐</p>
      <h3 style="font-weight:600;margin-bottom:8px;">特典2</h3>
      <p style="color:#666;font-size:0.9rem;">次回使える1,000円クーポン</p>
    </div>
    <div style="background:#fafafa;padding:24px;border-radius:12px;text-align:center;">
      <p style="font-size:2rem;margin-bottom:8px;">⭐</p>
      <h3 style="font-weight:600;margin-bottom:8px;">特典3</h3>
      <p style="color:#666;font-size:0.9rem;">アメニティセットプレゼント</p>
    </div>
  </div>
</section>

<section style="padding:40px 20px;text-align:center;background:#f8f6f2;">
  <p style="margin-bottom:16px;color:#666;">お早めにご予約ください</p>
  <a href="/" style="display:inline-block;background:#e74c3c;color:#fff;padding:16px 48px;border-radius:30px;font-size:1.1rem;font-weight:600;text-decoration:none;">今すぐ予約する</a>
</section>
''',
        'css_content': '''
body { font-family: "Noto Sans JP", sans-serif; }
a:hover { opacity: 0.85; transform: translateY(-1px); }
''',
        'grapesjs_data': {},
    },
    {
        'name': 'スタッフ紹介ページ',
        'description': 'スタッフのプロフィール・得意分野・メッセージを紹介するページ。',
        'category': 'salon',
        'html_content': '''
<div style="max-width:800px;margin:0 auto;padding:40px 20px;">
  <h1 style="font-size:1.8rem;font-weight:700;color:#8c876c;text-align:center;margin-bottom:40px;">スタッフ紹介</h1>

  <div style="display:flex;flex-wrap:wrap;gap:32px;align-items:flex-start;margin-bottom:48px;padding:32px;background:#f8f6f2;border-radius:16px;">
    <div style="width:200px;height:200px;border-radius:50%;background:#ddd;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:4rem;color:#aaa;margin:0 auto;">
      👤
    </div>
    <div style="flex:1;min-width:250px;">
      <h2 style="font-size:1.5rem;font-weight:700;color:#8c876c;margin-bottom:8px;">スタッフ名</h2>
      <p style="color:#999;font-size:0.9rem;margin-bottom:16px;">チーフスタイリスト / 経験10年</p>
      <p style="line-height:1.8;color:#555;">
        お客様の魅力を最大限に引き出すスタイルをご提案いたします。
        カウンセリングを大切にし、一人ひとりに合ったプランをご用意しています。
      </p>
      <div style="margin-top:16px;">
        <span style="display:inline-block;background:#8c876c;color:#fff;padding:4px 12px;border-radius:20px;font-size:0.8rem;margin:4px 4px 4px 0;">カット</span>
        <span style="display:inline-block;background:#8c876c;color:#fff;padding:4px 12px;border-radius:20px;font-size:0.8rem;margin:4px 4px 4px 0;">カラー</span>
        <span style="display:inline-block;background:#8c876c;color:#fff;padding:4px 12px;border-radius:20px;font-size:0.8rem;margin:4px 4px 4px 0;">ヘッドスパ</span>
      </div>
    </div>
  </div>

  <div style="text-align:center;">
    <a href="/" style="display:inline-block;background:#8c876c;color:#fff;padding:12px 36px;border-radius:30px;font-weight:600;text-decoration:none;">このスタッフに予約する</a>
  </div>
</div>
''',
        'css_content': '''
body { font-family: "Noto Sans JP", sans-serif; }
''',
        'grapesjs_data': {},
    },
    {
        'name': 'メニュー・料金表',
        'description': 'サービスメニューと料金を分かりやすく一覧表示するページ。',
        'category': 'general',
        'html_content': '''
<div style="max-width:800px;margin:0 auto;padding:40px 20px;">
  <h1 style="font-size:1.8rem;font-weight:700;color:#8c876c;text-align:center;margin-bottom:8px;">メニュー・料金表</h1>
  <p style="text-align:center;color:#999;margin-bottom:40px;">※ 価格はすべて税込です</p>

  <div style="margin-bottom:40px;">
    <h2 style="font-size:1.3rem;font-weight:700;color:#8c876c;border-bottom:2px solid #8c876c;padding-bottom:8px;margin-bottom:20px;">カットメニュー</h2>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>カット</span><span style="font-weight:600;">¥5,500</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>カット + シャンプーブロー</span><span style="font-weight:600;">¥6,600</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>前髪カット</span><span style="font-weight:600;">¥1,100</span>
    </div>
  </div>

  <div style="margin-bottom:40px;">
    <h2 style="font-size:1.3rem;font-weight:700;color:#8c876c;border-bottom:2px solid #8c876c;padding-bottom:8px;margin-bottom:20px;">カラーメニュー</h2>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>リタッチカラー</span><span style="font-weight:600;">¥5,500</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>フルカラー</span><span style="font-weight:600;">¥7,700</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>ハイライト</span><span style="font-weight:600;">¥8,800〜</span>
    </div>
  </div>

  <div style="margin-bottom:40px;">
    <h2 style="font-size:1.3rem;font-weight:700;color:#8c876c;border-bottom:2px solid #8c876c;padding-bottom:8px;margin-bottom:20px;">トリートメント</h2>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>クイックトリートメント</span><span style="font-weight:600;">¥2,200</span>
    </div>
    <div style="display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;">
      <span>プレミアムトリートメント</span><span style="font-weight:600;">¥4,400</span>
    </div>
  </div>

  <div style="background:#f8f6f2;padding:24px;border-radius:12px;text-align:center;">
    <p style="margin-bottom:12px;color:#666;">ご予約・お問い合わせ</p>
    <a href="/" style="display:inline-block;background:#8c876c;color:#fff;padding:12px 36px;border-radius:30px;font-weight:600;text-decoration:none;">予約ページへ</a>
  </div>
</div>
''',
        'css_content': '''
body { font-family: "Noto Sans JP", sans-serif; }
''',
        'grapesjs_data': {},
    },
    {
        'name': 'お問い合わせページ',
        'description': 'お問い合わせフォーム付きのページ。営業時間・アクセス情報も掲載。',
        'category': 'general',
        'html_content': '''
<div style="max-width:700px;margin:0 auto;padding:40px 20px;">
  <h1 style="font-size:1.8rem;font-weight:700;color:#8c876c;text-align:center;margin-bottom:40px;">お問い合わせ</h1>

  <div style="background:#f8f6f2;padding:32px;border-radius:16px;margin-bottom:40px;">
    <h2 style="font-size:1.2rem;font-weight:600;color:#8c876c;margin-bottom:16px;">店舗情報</h2>
    <table style="width:100%;border-collapse:collapse;">
      <tr style="border-bottom:1px solid #e0ddd4;">
        <td style="padding:12px 0;font-weight:600;width:120px;color:#666;">住所</td>
        <td style="padding:12px 0;">東京都新宿区〇〇 1-2-3 △△ビル 4F</td>
      </tr>
      <tr style="border-bottom:1px solid #e0ddd4;">
        <td style="padding:12px 0;font-weight:600;color:#666;">電話番号</td>
        <td style="padding:12px 0;">03-1234-5678</td>
      </tr>
      <tr style="border-bottom:1px solid #e0ddd4;">
        <td style="padding:12px 0;font-weight:600;color:#666;">営業時間</td>
        <td style="padding:12px 0;">10:00〜20:00（最終受付 19:00）</td>
      </tr>
      <tr>
        <td style="padding:12px 0;font-weight:600;color:#666;">定休日</td>
        <td style="padding:12px 0;">毎週火曜日</td>
      </tr>
    </table>
  </div>

  <form style="background:#fff;padding:32px;border:1px solid #e0ddd4;border-radius:16px;">
    <h2 style="font-size:1.2rem;font-weight:600;color:#8c876c;margin-bottom:24px;">お問い合わせフォーム</h2>
    <div style="margin-bottom:20px;">
      <label style="display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;color:#555;">お名前 <span style="color:#e74c3c;">*</span></label>
      <input type="text" placeholder="山田 太郎" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:1rem;">
    </div>
    <div style="margin-bottom:20px;">
      <label style="display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;color:#555;">メールアドレス <span style="color:#e74c3c;">*</span></label>
      <input type="email" placeholder="example@email.com" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:1rem;">
    </div>
    <div style="margin-bottom:20px;">
      <label style="display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;color:#555;">電話番号</label>
      <input type="tel" placeholder="090-1234-5678" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:1rem;">
    </div>
    <div style="margin-bottom:24px;">
      <label style="display:block;font-weight:600;margin-bottom:6px;font-size:0.9rem;color:#555;">お問い合わせ内容 <span style="color:#e74c3c;">*</span></label>
      <textarea rows="5" placeholder="お問い合わせ内容をご記入ください" style="width:100%;padding:10px 14px;border:1px solid #d1d5db;border-radius:8px;font-size:1rem;resize:vertical;"></textarea>
    </div>
    <button type="submit" style="display:block;width:100%;background:#8c876c;color:#fff;padding:14px;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;">送信する</button>
  </form>
</div>
''',
        'css_content': '''
body { font-family: "Noto Sans JP", sans-serif; }
input:focus, textarea:focus { outline: none; border-color: #8c876c; box-shadow: 0 0 0 2px rgba(140,135,108,0.2); }
button:hover { opacity: 0.9; }
''',
        'grapesjs_data': {},
    },
]


class Command(BaseCommand):
    help = 'Seed 5 system page templates for the page builder'

    def handle(self, *args, **options):
        created_count = 0
        for tpl_data in TEMPLATES:
            _, created = PageTemplate.objects.update_or_create(
                name=tpl_data['name'],
                is_system=True,
                defaults={
                    'description': tpl_data['description'],
                    'category': tpl_data['category'],
                    'html_content': tpl_data['html_content'],
                    'css_content': tpl_data['css_content'],
                    'grapesjs_data': tpl_data['grapesjs_data'],
                },
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {tpl_data["name"]}'))
            else:
                self.stdout.write(f'  Updated: {tpl_data["name"]}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone: {created_count} created, {len(TEMPLATES) - created_count} updated'
        ))
