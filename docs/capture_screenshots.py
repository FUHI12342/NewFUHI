#!/usr/bin/env python3
"""
全画面キャプチャスクリプト（Playwright使用）
管理画面・フロントエンド・ダッシュボード等のスクリーンショットを一括取得する。

Usage:
    cd ~/NewFUHI
    .venv/bin/python docs/capture_screenshots.py
"""
import os
import sys
import time

# Django setup
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

from playwright.sync_api import sync_playwright

BASE_URL = 'http://127.0.0.1:8899'
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screenshots')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Admin credentials
ADMIN_USER = 'demo_owner'
ADMIN_PASS = 'demo1234'


def screenshot(page, path, name, full_page=True, wait_ms=500):
    """ページのスクリーンショットを保存"""
    url = f'{BASE_URL}{path}'
    try:
        page.goto(url, wait_until='networkidle', timeout=15000)
        page.wait_for_timeout(wait_ms)
        filepath = os.path.join(OUTPUT_DIR, f'{name}.png')
        page.screenshot(path=filepath, full_page=full_page)
        print(f'  OK: {name}.png ({path})')
        return True
    except Exception as e:
        print(f'  FAIL: {name} ({path}) - {e}')
        return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── 管理画面セッション（1280x900 デスクトップ）──
        admin_ctx = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ja-JP',
        )
        admin = admin_ctx.new_page()

        # ログイン
        admin.goto(f'{BASE_URL}/admin/login/', wait_until='networkidle')
        admin.fill('#id_username', ADMIN_USER)
        admin.fill('#id_password', ADMIN_PASS)
        admin.click('input[type="submit"]')
        admin.wait_for_load_state('networkidle')
        print('Admin login OK')

        # ── 管理画面スクリーンショット ──
        print('\n[管理画面]')

        # ダッシュボード（ホーム）
        screenshot(admin, '/admin/', 'admin_home')

        # 売上ダッシュボード
        screenshot(admin, '/admin/dashboard/sales/', 'dashboard_sales', wait_ms=2000)

        # シフトカレンダー
        screenshot(admin, '/admin/shift/calendar/', 'shift_calendar', wait_ms=1500)

        # 本日のシフト
        screenshot(admin, '/admin/shift/today/', 'shift_today', wait_ms=1000)

        # POS レジ
        screenshot(admin, '/admin/pos/', 'pos', wait_ms=1000)

        # キッチンディスプレイ
        screenshot(admin, '/admin/pos/kitchen/', 'kitchen_display', wait_ms=1000)

        # QR勤怠
        screenshot(admin, '/admin/attendance/qr/', 'attendance_qr', wait_ms=1000)

        # PIN打刻
        screenshot(admin, '/admin/attendance/pin/', 'attendance_pin', wait_ms=500)

        # 出退勤ボード
        screenshot(admin, '/admin/attendance/board/', 'attendance_board', wait_ms=1000)

        # 勤務実績
        screenshot(admin, '/admin/attendance/performance/', 'attendance_performance', wait_ms=1000)

        # 在庫管理
        screenshot(admin, '/admin/inventory/', 'inventory', wait_ms=1000)

        # EC注文管理
        screenshot(admin, '/admin/ec/orders/', 'ec_orders', wait_ms=1000)

        # 来客分析
        screenshot(admin, '/admin/analytics/visitors/', 'visitor_analytics', wait_ms=1500)

        # AI推薦
        screenshot(admin, '/admin/ai/recommendation/', 'ai_recommendation', wait_ms=1500)

        # IoTセンサー
        screenshot(admin, '/admin/iot/sensors/', 'iot_sensors', wait_ms=1500)

        # チェックインスキャン
        screenshot(admin, '/admin/checkin/scan/', 'checkin_scan', wait_ms=500)

        # デバッグパネル
        screenshot(admin, '/admin/debug/', 'debug_panel', wait_ms=1000)

        # ── モデル一覧画面 ──
        print('\n[モデル管理画面]')

        # 予約一覧
        screenshot(admin, '/admin/booking/schedule/', 'schedule_list', wait_ms=500)

        # スタッフ一覧
        screenshot(admin, '/admin/booking/staff/', 'staff_list', wait_ms=500)

        # シフト期間一覧
        screenshot(admin, '/admin/booking/shiftperiod/', 'shift_period_list', wait_ms=500)

        # シフト交代申請
        screenshot(admin, '/admin/booking/shiftswaprequest/', 'shift_swap_list', wait_ms=500)

        # シフト空き
        screenshot(admin, '/admin/booking/shiftvacancy/', 'shift_vacancy_list', wait_ms=500)

        # 定休日
        screenshot(admin, '/admin/booking/storecloseddate/', 'store_closed_date', wait_ms=500)

        # 顧客フィードバック（NPS）
        screenshot(admin, '/admin/booking/customerfeedback/', 'customer_feedback', wait_ms=500)

        # セキュリティログ
        screenshot(admin, '/admin/booking/securitylog/', 'security_log', wait_ms=500)

        # ビジネスインサイト
        screenshot(admin, '/admin/booking/businessinsight/', 'business_insight', wait_ms=500)

        # 商品一覧
        screenshot(admin, '/admin/booking/product/', 'product_list', wait_ms=500)

        # 注文一覧
        screenshot(admin, '/admin/booking/order/', 'order_list', wait_ms=500)

        # 給与期間一覧
        screenshot(admin, '/admin/booking/payrollperiod/', 'payroll_list', wait_ms=500)

        # スタッフ評価
        screenshot(admin, '/admin/booking/staffevaluation/', 'staff_evaluation', wait_ms=500)

        # サイト設定
        screenshot(admin, '/admin/booking/sitesettings/', 'site_settings', wait_ms=500)

        # セキュリティ監査
        screenshot(admin, '/admin/booking/securityaudit/', 'security_audit', wait_ms=500)

        admin_ctx.close()

        # ── フロントエンド（モバイル幅） ──
        front_ctx = browser.new_context(
            viewport={'width': 390, 'height': 844},
            locale='ja-JP',
        )
        front = front_ctx.new_page()

        print('\n[フロントエンド]')

        # トップページ
        screenshot(front, '/ja/', 'front_top', wait_ms=1000)

        # 店舗ページ（スタッフ一覧）
        screenshot(front, '/ja/store/1/staffs/', 'front_staff_list', wait_ms=1000)

        # お知らせ一覧
        screenshot(front, '/ja/news/', 'front_news', wait_ms=500)

        # ECショップ
        screenshot(front, '/ja/shop/', 'front_shop', wait_ms=1000)

        # 勤怠打刻ページ
        screenshot(front, '/ja/attendance/stamp/', 'front_attendance_stamp', wait_ms=500)

        front_ctx.close()

        # ── テーブルオーダー ──
        # テーブルのUUIDを取得
        import django
        django.setup()
        from booking.models import TableSeat
        table = TableSeat.objects.filter(is_active=True).first()
        if table:
            table_ctx = browser.new_context(
                viewport={'width': 390, 'height': 844},
                locale='ja-JP',
            )
            table_page = table_ctx.new_page()
            print('\n[テーブルオーダー]')
            screenshot(table_page, f'/t/{table.id}/', 'table_order', wait_ms=1000)
            table_ctx.close()

        browser.close()

    # ── 結果サマリ ──
    files = sorted(os.listdir(OUTPUT_DIR))
    pngs = [f for f in files if f.endswith('.png')]
    print(f'\n=== 完了: {len(pngs)}枚のスクリーンショットを保存 ===')
    print(f'出力先: {OUTPUT_DIR}/')
    for f in pngs:
        size = os.path.getsize(os.path.join(OUTPUT_DIR, f))
        print(f'  {f} ({size / 1024:.0f} KB)')


if __name__ == '__main__':
    main()
