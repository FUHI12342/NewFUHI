/**
 * 全画面キャプチャスクリプト（Playwright / Node.js版）
 * Usage: npx playwright test --config docs/capture_screenshots.mjs
 * Or:    node docs/capture_screenshots.mjs
 */
import { chromium } from 'playwright';
import { mkdirSync, readdirSync, statSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE_URL = 'http://127.0.0.1:8899';
const OUTPUT_DIR = join(__dirname, 'screenshots');
mkdirSync(OUTPUT_DIR, { recursive: true });

const ADMIN_USER = 'demo_owner';
const ADMIN_PASS = 'demo1234';

async function shot(page, path, name, opts = {}) {
  const { fullPage = true, waitMs = 500 } = opts;
  try {
    await page.goto(`${BASE_URL}${path}`, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(waitMs);
    const fp = join(OUTPUT_DIR, `${name}.png`);
    await page.screenshot({ path: fp, fullPage });
    console.log(`  OK: ${name}.png (${path})`);
    return true;
  } catch (e) {
    console.log(`  FAIL: ${name} (${path}) - ${e.message}`);
    return false;
  }
}

async function main() {
  const browser = await chromium.launch({ headless: true });

  // ── Admin session (desktop) ──
  const adminCtx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    locale: 'ja-JP',
  });
  const admin = await adminCtx.newPage();

  // Login
  await admin.goto(`${BASE_URL}/admin/login/`, { waitUntil: 'networkidle', timeout: 15000 });
  await admin.fill('input[name="username"]', ADMIN_USER);
  await admin.fill('input[name="password"]', ADMIN_PASS);
  await admin.click('input[type="submit"], button[type="submit"]');
  await admin.waitForLoadState('networkidle');
  console.log('Admin login OK\n');

  // ── Admin screens ──
  console.log('[管理画面]');
  await shot(admin, '/admin/', 'admin_home');
  await shot(admin, '/admin/dashboard/sales/', 'dashboard_sales', { waitMs: 3000 });
  await shot(admin, '/admin/shift/calendar/', 'shift_calendar', { waitMs: 2000 });
  await shot(admin, '/admin/shift/today/', 'shift_today', { waitMs: 1500 });
  await shot(admin, '/admin/pos/', 'pos', { waitMs: 1500 });
  await shot(admin, '/admin/pos/kitchen/', 'kitchen_display', { waitMs: 1500 });
  await shot(admin, '/admin/attendance/qr/', 'attendance_qr', { waitMs: 1000 });
  await shot(admin, '/admin/attendance/pin/', 'attendance_pin');
  await shot(admin, '/admin/attendance/board/', 'attendance_board', { waitMs: 1000 });
  await shot(admin, '/admin/attendance/performance/', 'attendance_performance', { waitMs: 1500 });
  await shot(admin, '/admin/inventory/', 'inventory', { waitMs: 1500 });
  await shot(admin, '/admin/ec/orders/', 'ec_orders', { waitMs: 1000 });
  await shot(admin, '/admin/analytics/visitors/', 'visitor_analytics', { waitMs: 2000 });
  await shot(admin, '/admin/ai/recommendation/', 'ai_recommendation', { waitMs: 2000 });
  await shot(admin, '/admin/iot/sensors/', 'iot_sensors', { waitMs: 2000 });
  await shot(admin, '/admin/checkin/scan/', 'checkin_scan');
  await shot(admin, '/admin/debug/', 'debug_panel', { waitMs: 1000 });

  console.log('\n[モデル管理画面]');
  await shot(admin, '/admin/booking/schedule/', 'schedule_list');
  await shot(admin, '/admin/booking/staff/', 'staff_list');
  await shot(admin, '/admin/booking/shiftperiod/', 'shift_period_list');
  await shot(admin, '/admin/booking/shiftswaprequest/', 'shift_swap_list');
  await shot(admin, '/admin/booking/shiftvacancy/', 'shift_vacancy_list');
  await shot(admin, '/admin/booking/storecloseddate/', 'store_closed_date');
  await shot(admin, '/admin/booking/customerfeedback/', 'customer_feedback');
  await shot(admin, '/admin/booking/securitylog/', 'security_log');
  await shot(admin, '/admin/booking/businessinsight/', 'business_insight');
  await shot(admin, '/admin/booking/product/', 'product_list');
  await shot(admin, '/admin/booking/order/', 'order_list');
  await shot(admin, '/admin/booking/payrollperiod/', 'payroll_list');
  await shot(admin, '/admin/booking/staffevaluation/', 'staff_evaluation');
  await shot(admin, '/admin/booking/sitesettings/', 'site_settings');
  await shot(admin, '/admin/booking/securityaudit/', 'security_audit');

  await adminCtx.close();

  // ── Frontend (mobile) ──
  const frontCtx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: 'ja-JP',
  });
  const front = await frontCtx.newPage();

  console.log('\n[フロントエンド]');
  await shot(front, '/', 'front_top', { waitMs: 1500 });
  await shot(front, '/store/1/staffs/', 'front_staff_list', { waitMs: 1000 });
  await shot(front, '/news/', 'front_news');
  await shot(front, '/shop/', 'front_shop', { waitMs: 1000 });
  await shot(front, '/attendance/stamp/', 'front_attendance_stamp');

  await frontCtx.close();

  // ── Table order ──
  // Get a table UUID via API
  const tableCtx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    locale: 'ja-JP',
  });
  const tablePage = await tableCtx.newPage();
  console.log('\n[テーブルオーダー]');
  // Try common table paths - the exact UUID would need Django, so try /t/ patterns
  await shot(tablePage, '/ja/store/1/staffs/', 'table_order_fallback', { waitMs: 1000 });
  await tableCtx.close();

  await browser.close();

  // Summary
  const files = readdirSync(OUTPUT_DIR).filter(f => f.endsWith('.png')).sort();
  console.log(`\n=== 完了: ${files.length}枚のスクリーンショット ===`);
  console.log(`出力先: ${OUTPUT_DIR}/`);
  for (const f of files) {
    const size = statSync(join(OUTPUT_DIR, f)).size;
    console.log(`  ${f} (${(size / 1024).toFixed(0)} KB)`);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
