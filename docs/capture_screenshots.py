#!/usr/bin/env python3
"""UI スクリーンショット撮影スクリプト — ローカルサーバーで各画面をキャプチャ"""
import os
import sys
import subprocess
import time

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings.local')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import date

User = get_user_model()

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

BASE_URL = 'http://127.0.0.1:8765'


def setup_test_data():
    """テスト用データを作成"""
    from booking.models import (
        Store, Staff, DraftPost, KnowledgeEntry, SiteSettings,
        SocialAccount,
    )

    # Store
    store, _ = Store.objects.get_or_create(
        name='占いサロン チャンス 渋谷店',
        defaults={
            'address': '東京都渋谷区道玄坂1-2-3',
            'business_hours': '11:00〜22:00',
            'nearest_station': '渋谷駅 徒歩3分',
            'description': 'タロット・西洋占星術・手相の占いサロン',
            'embed_api_key': 'demo-api-key-abc123xyz',
            'embed_allowed_domains': 'https://example-wordpress.com',
        },
    )
    # 既存Storeでも embed_api_key を確実に設定
    if not store.embed_api_key:
        store.embed_api_key = 'demo-api-key-abc123xyz'
        store.embed_allowed_domains = 'https://example-wordpress.com'
        store.save(update_fields=['embed_api_key', 'embed_allowed_domains'])

    # SiteSettings
    ss = SiteSettings.load()
    ss.embed_enabled = True
    ss.save()

    # Admin user
    admin, created = User.objects.get_or_create(
        username='demo_admin',
        defaults={'email': 'admin@demo.com', 'is_superuser': True, 'is_staff': True},
    )
    if created:
        admin.set_password('demopass123')
        admin.save()

    # Staff / Casts (user_id required)
    cast_data = [
        ('月見 あかり', 'akari', 'タロット歴15年。恋愛・仕事の悩みを丁寧に読み解きます。'),
        ('星野 ゆき', 'yuki', '西洋占星術とオラクルカードで未来を照らします。'),
        ('桜井 りな', 'rina', '手相・人相学の第一人者。TV出演多数。'),
    ]
    for name, username, intro in cast_data:
        user, _ = User.objects.get_or_create(
            username=f'cast_{username}',
            defaults={'email': f'{username}@demo.com'},
        )
        Staff.objects.get_or_create(
            name=name, store=store,
            defaults={
                'user': user,
                'introduction': intro,
                'staff_type': 'fortune_teller',
            },
        )

    # Knowledge entries
    KnowledgeEntry.objects.get_or_create(
        store=store, category='store_info', title='店舗PR文',
        defaults={'content': '渋谷駅徒歩3分。完全個室でプライバシーを守ります。'},
    )
    KnowledgeEntry.objects.get_or_create(
        store=store, category='campaign', title='春の新規割引',
        defaults={'content': '3月末まで初回20%OFF！お気軽にお試しください。'},
    )
    KnowledgeEntry.objects.get_or_create(
        store=store, category='cast_profile', title='月見あかり先生',
        defaults={'content': 'タロット歴15年のベテラン。恋愛成就率90%以上と評判。'},
    )

    # Draft posts - Instagram (long)
    DraftPost.objects.get_or_create(
        store=store, status='generated', target_date=date.today(),
        platforms=['instagram'],
        defaults={
            'content': (
                '✨本日の出勤情報✨\n\n'
                '占いサロン チャンス 渋谷店より\n'
                '本日の出勤キャストをご紹介🔮\n\n'
                '🌙 月見あかり先生 (11:00-18:00)\n'
                'タロット歴15年！恋愛のお悩みはおまかせ💕\n\n'
                '⭐ 星野ゆき先生 (13:00-21:00)\n'
                '西洋占星術で未来を照らします✨\n\n'
                '🌸 桜井りな先生 (15:00-22:00)\n'
                'TV出演多数の実力派！手相鑑定🖐️\n\n'
                'ご予約お待ちしております！\n\n'
                '#占いサロン #渋谷占い #タロット #当たる占い #恋愛占い '
                '#西洋占星術 #手相 #占い好きな人と繋がりたい'
            ),
            'ai_generated_content': '(AI generated)',
            'quality_score': 0.82,
            'quality_feedback': (
                'AI評価: 店舗名・キャスト名が正確に記載されており、'
                '絵文字の使い方も適切です。ハッシュタグも十分です。'
            ),
        },
    )
    # Draft - X (short)
    DraftPost.objects.get_or_create(
        store=store, status='generated', target_date=date.today(),
        platforms=['x'],
        defaults={
            'content': (
                '✨本日の出勤✨ 月見あかり先生が11時からお待ちしております！'
                '恋愛のお悩み、タロットで丁寧に読み解きます🔮 '
                'お気軽にご予約ください💕 #占いサロン #渋谷'
            ),
            'ai_generated_content': '(AI generated)',
            'quality_score': 0.91,
            'quality_feedback': (
                'AI評価: 簡潔で魅力的なX向け投稿です。'
                '加重文字数も280以内に収まっています。'
            ),
        },
    )
    # Posted draft
    DraftPost.objects.get_or_create(
        store=store, status='posted', target_date=date.today(),
        platforms=['x'],
        defaults={
            'content': '占いサロンチャンス渋谷店🔮 本日も元気に営業中！桜井りな先生の手相鑑定が大人気✨ #占い',
            'ai_generated_content': '(AI generated)',
            'quality_score': 0.75,
            'quality_feedback': '',
            'posted_at': timezone.now(),
        },
    )

    # SocialAccount
    SocialAccount.objects.get_or_create(
        store=store, platform='x',
        defaults={'account_name': 'chance_shibuya', 'is_active': True},
    )

    print(f'Test data ready: store={store.pk}, drafts={DraftPost.objects.count()}')
    return store, admin


def capture_screenshots():
    """Playwright で各画面のスクリーンショットを撮影"""
    from booking.models import Store, SiteSettings
    # Playwright 外で DB クエリ実行（async context 回避）
    store = Store.objects.filter(name__contains='チャンス').first()
    store_pk = store.pk if store else 1
    embed_api_key = store.embed_api_key if store else ''
    ss = SiteSettings.load()
    ss_pk = ss.pk

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={'width': 1400, 'height': 900},
            device_scale_factor=2,
        )
        page = context.new_page()

        # ログイン
        print('Logging in...')
        page.goto(f'{BASE_URL}/admin/login/')
        page.wait_for_load_state('networkidle')
        page.fill('input[name="username"]', 'demo_admin')
        page.fill('input[name="password"]', 'demopass123')
        page.click('button[type="submit"], input[type="submit"]')
        page.wait_for_load_state('networkidle')
        time.sleep(1)

        screenshots = {}

        # 1. SNS下書き管理 一覧
        print('  [1/9] Draft list...')
        page.goto(f'{BASE_URL}/admin/social/drafts/')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        path = os.path.join(SCREENSHOTS_DIR, '01_draft_list.png')
        page.screenshot(path=path, full_page=True)
        screenshots['draft_list'] = path

        # 2. 下書き編集モード
        print('  [2/9] Draft edit mode...')
        edit_buttons = page.locator('button:has-text("編集")')
        if edit_buttons.count() > 0:
            edit_buttons.first.click()
            time.sleep(0.5)
        path = os.path.join(SCREENSHOTS_DIR, '02_draft_edit.png')
        page.screenshot(path=path, full_page=True)
        screenshots['draft_edit'] = path

        # 3. AI下書き生成画面
        print('  [3/9] Generate form...')
        page.goto(f'{BASE_URL}/admin/social/drafts/generate/')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        path = os.path.join(SCREENSHOTS_DIR, '03_generate_form.png')
        page.screenshot(path=path, full_page=True)
        screenshots['generate_form'] = path

        # 4. SNSナレッジ
        print('  [4/9] Knowledge admin...')
        page.goto(f'{BASE_URL}/admin/booking/knowledgeentry/')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        path = os.path.join(SCREENSHOTS_DIR, '04_knowledge_list.png')
        page.screenshot(path=path, full_page=True)
        screenshots['knowledge_list'] = path

        # 5. 店舗設定 (embed)
        print('  [5/9] Store embed settings...')
        if store_pk:
            page.goto(f'{BASE_URL}/admin/booking/store/{store_pk}/change/')
            page.wait_for_load_state('networkidle')
            time.sleep(1)
            # collapse セクションを開く
            toggles = page.locator('.collapse-toggle')
            for i in range(toggles.count()):
                try:
                    toggles.nth(i).click()
                    time.sleep(0.2)
                except Exception:
                    pass
            time.sleep(0.5)
            path = os.path.join(SCREENSHOTS_DIR, '05_store_embed.png')
            page.screenshot(path=path, full_page=True)
            screenshots['store_embed'] = path

        # 6. SNSアカウント（ビューポート内のみ撮影）
        print('  [6/9] Social accounts...')
        page.goto(f'{BASE_URL}/admin/booking/socialaccount/')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        path = os.path.join(SCREENSHOTS_DIR, '06_social_accounts.png')
        page.screenshot(path=path, full_page=False)
        screenshots['social_accounts'] = path

        # 7. サイト設定
        print('  [7/9] Site settings...')
        page.goto(f'{BASE_URL}/admin/booking/sitesettings/{ss_pk}/change/')
        page.wait_for_load_state('networkidle')
        time.sleep(1)
        path = os.path.join(SCREENSHOTS_DIR, '07_site_settings.png')
        page.screenshot(path=path, full_page=True)
        screenshots['site_settings'] = path

        # 8. Embed: 予約カレンダー
        print('  [8/9] Embed booking...')
        if store_pk:
            page.goto(f'{BASE_URL}/embed/booking/{store_pk}/?api_key={embed_api_key}')
            page.wait_for_load_state('networkidle')
            time.sleep(1)
            path = os.path.join(SCREENSHOTS_DIR, '08_embed_booking.png')
            page.screenshot(path=path, full_page=True)
            screenshots['embed_booking'] = path

        # 9. Embed: シフト表示
        print('  [9/9] Embed shift...')
        if store_pk:
            page.goto(f'{BASE_URL}/embed/shift/{store_pk}/?api_key={embed_api_key}')
            page.wait_for_load_state('networkidle')
            time.sleep(1)
            path = os.path.join(SCREENSHOTS_DIR, '09_embed_shift.png')
            page.screenshot(path=path, full_page=True)
            screenshots['embed_shift'] = path

        browser.close()
        print(f'\nAll screenshots captured: {len(screenshots)} files')
        return screenshots


def main():
    store, admin = setup_test_data()

    # 既にサーバーが起動していれば再利用、なければ起動
    import urllib.request
    server_proc = None
    try:
        urllib.request.urlopen(f'{BASE_URL}/admin/login/', timeout=2)
        print('Using existing server.')
    except Exception:
        print('Starting local Django server on port 8765...')
        server_proc = subprocess.Popen(
            [sys.executable, 'manage.py', 'runserver', '8765', '--noreload'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        for i in range(15):
            try:
                urllib.request.urlopen(f'{BASE_URL}/admin/login/', timeout=2)
                print(f'Server ready (attempt {i+1})')
                break
            except Exception:
                time.sleep(1)
        else:
            print('Server failed to start!')
            server_proc.terminate()
            return {}

    try:
        screenshots = capture_screenshots()
    finally:
        if server_proc:
            server_proc.terminate()
            server_proc.wait(timeout=5)
            print('Server stopped.')

    return screenshots


if __name__ == '__main__':
    result = main()
    for name, path in result.items():
        print(f'  {name}: {path}')
