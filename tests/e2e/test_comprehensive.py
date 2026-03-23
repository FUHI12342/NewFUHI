#!/usr/bin/env python3
"""Comprehensive E2E Test Suite — timebaibai.com (production)

Covers ALL pages, APIs, mobile responsive, CSRF validation,
network errors, form presence, and i18n. Read-only (no data mutations).

Run: /usr/bin/python3 /tmp/e2e/test_comprehensive.py
"""
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = "https://timebaibai.com"
SCREENSHOT_DIR = "/tmp/e2e/comprehensive"
DELAY = 2

ACCOUNTS = {
    "cast": {"username": "demo_fortune", "password": "demo1234"},
    "staff": {"username": "demo_staff", "password": "demo1234"},
    "manager": {"username": "demo_manager", "password": "demo1234"},
    "owner": {"username": "demo_owner", "password": "demo1234"},
}


@dataclass
class TestResult:
    test_id: str
    name: str
    status: str = "PENDING"
    notes: str = ""
    screenshot: str = ""
    js_errors: list = field(default_factory=list)
    network_errors: list = field(default_factory=list)


class ComprehensiveE2ERunner:
    def __init__(self):
        self.results = []
        self.pw = None
        self.browser = None
        self._sessions = {}
        self._current_ctx = None
        self._page = None
        self._js_errors = []
        self._network_errors = []

    # ─── Setup / Teardown ───

    def start(self):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)

    def stop(self):
        self._close_current()
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def _close_current(self):
        if self._current_ctx:
            try:
                self._current_ctx.close()
            except Exception:
                pass
            self._current_ctx = None
            self._page = None

    def _new_page(self, storage_state=None, viewport=None):
        self._close_current()
        self._js_errors = []
        self._network_errors = []
        vp = viewport or {"width": 1280, "height": 900}
        opts = {"viewport": vp, "ignore_https_errors": True}
        if storage_state:
            opts["storage_state"] = storage_state
        self._current_ctx = self.browser.new_context(**opts)
        self._page = self._current_ctx.new_page()
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_pageerror)
        self._page.on("response", self._on_response)
        return self._page

    def _on_console(self, msg):
        if msg.type == "error":
            text = msg.text
            # Filter known non-issues
            for skip in ["fonts.googleapis.com", "503", "Service Temporarily",
                         "Content Security Policy", "favicon.ico",
                         "Failed to load resource", "gstatic.com"]:
                if skip in text:
                    return
            self._js_errors.append(text)

    def _on_pageerror(self, err):
        self._js_errors.append(str(err))

    def _on_response(self, response):
        url = response.url
        status = response.status
        # Track failed requests (but skip external and common noise)
        if status >= 400:
            for skip in ["fonts.googleapis.com", "google-analytics",
                         "favicon.ico", "analytics", "gtag",
                         "gstatic.com", "lin.ee"]:
                if skip in url:
                    return
            self._network_errors.append({"url": url, "status": status})

    def _wait(self, secs=None):
        time.sleep(secs or DELAY)

    # ─── Session management ───

    def do_login(self, role):
        page = self._new_page()
        self._wait(5)
        page.goto(f"{BASE_URL}/login/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector('input[name="username"]', timeout=15000)
        creds = ACCOUNTS[role]
        page.fill('input[name="username"]', creds["username"])
        page.fill('input[name="password"]', creds["password"])
        page.click('button[type="submit"]')
        time.sleep(5)
        for _ in range(3):
            if self._page.url.endswith("/login/") or self._page.url.endswith("/login"):
                time.sleep(2)
            else:
                break
        url = self._page.url
        success = not url.endswith("/login/") and not url.endswith("/login")
        if success:
            if "/admin/" not in url:
                page.goto(f"{BASE_URL}/admin/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
            state_path = os.path.join(SCREENSHOT_DIR, f"state_{role}.json")
            self._current_ctx.storage_state(path=state_path)
            self._sessions[role] = state_path
        self._close_current()
        return success

    def use_session(self, role, viewport=None):
        state = self._sessions.get(role)
        return self._new_page(storage_state=state, viewport=viewport)

    def goto(self, path, timeout=30000):
        self._wait(1)
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        resp = self._page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        try:
            self._page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        return resp.status if resp else 0

    def screenshot(self, name):
        path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        try:
            self._page.screenshot(path=path, full_page=False)
        except Exception:
            pass
        return path

    def body_text(self):
        try:
            return self._page.inner_text("body")
        except Exception:
            return ""

    def page_html(self):
        try:
            return self._page.content()
        except Exception:
            return ""

    def get_js_errors(self):
        errors = self._js_errors.copy()
        self._js_errors.clear()
        return errors

    def get_network_errors(self):
        errors = self._network_errors.copy()
        self._network_errors.clear()
        return errors

    def add_result(self, test_id, name, status, notes="", screenshot=""):
        js = self.get_js_errors()
        net = self.get_network_errors()
        r = TestResult(test_id=test_id, name=name, status=status,
                       notes=notes, screenshot=screenshot,
                       js_errors=js, network_errors=net)
        self.results.append(r)
        icon = {"PASS": "OK", "FAIL": "NG", "SKIP": "--"}.get(status, "??")
        print(f"  [{icon}] {test_id}: {name} — {notes[:130]}")
        if js:
            for e in js[:2]:
                print(f"    JS: {e[:100]}")
        if net:
            for e in net[:2]:
                print(f"    NET: {e['status']} {e['url'][-80:]}")

    # ─── Helper: check page load ───

    def _check_page(self, tid, name, path, role=None, keywords=None,
                    expect_status=200, viewport=None, ss_prefix=""):
        """Generic page load test. Returns (status, text)."""
        try:
            if role:
                self.use_session(role, viewport=viewport)
            elif viewport:
                self._new_page(viewport=viewport)
            status = self.goto(path)
            text = self.body_text()
            ss_name = f"{ss_prefix}{tid}" if ss_prefix else tid
            ss = self.screenshot(ss_name)

            ok = status == expect_status
            kw_notes = ""
            if keywords:
                found = [kw for kw in keywords if kw in text]
                missing = [kw for kw in keywords if kw not in text]
                if missing:
                    ok = False
                kw_notes = f", Found:{found}" if found else ""
                if missing:
                    kw_notes += f", Missing:{missing}"

            notes = f"Status:{status}{kw_notes}"
            self.add_result(tid, name, "PASS" if ok else "FAIL", notes, ss)
            if role:
                self._close_current()
            return status, text
        except Exception as e:
            self.add_result(tid, name, "FAIL", str(e)[:200])
            if role:
                self._close_current()
            return 0, ""

    # ─── Helper: check API endpoint ───

    def _check_api(self, tid, name, path, role=None, method="GET", expect_status=200):
        """API smoke test via fetch()."""
        try:
            if role:
                self.use_session(role)
                # Navigate to admin first to set up cookies for same-origin
                self.goto("/admin/")
                self._wait(1)

            result = self._page.evaluate(f"""async () => {{
                const resp = await fetch('{BASE_URL}{path}', {{
                    method: '{method}',
                    credentials: 'same-origin',
                    headers: {{'Accept': 'application/json'}},
                }});
                return {{status: resp.status, ok: resp.ok}};
            }}""")
            status = result["status"]
            ok = status == expect_status
            notes = f"Status:{status}, Expected:{expect_status}"
            self.add_result(tid, name, "PASS" if ok else "FAIL", notes)
            if role:
                self._close_current()
            return status
        except Exception as e:
            self.add_result(tid, name, "FAIL", str(e)[:200])
            if role:
                self._close_current()
            return 0

    # ═══════════════════════════════════════════
    # Phase 6: ALL Public Pages
    # ═══════════════════════════════════════════
    def phase6_public_pages(self):
        print("\n=== Phase 6: All Public Pages ===")
        self._new_page()
        pages = [
            ("P6.1", "トップ", "/", ["占い"]),
            ("P6.2", "店舗一覧", "/stores/", []),
            ("P6.3", "占い師一覧", "/fortune-tellers/", []),
            ("P6.4", "日付カレンダー", "/date-calendar/", []),
            ("P6.5", "ショップ", "/shop/", []),
            ("P6.6", "ニュース", "/news/", []),
            ("P6.7", "ヘルプ", "/help/", []),
            ("P6.8", "プライバシーポリシー", "/privacy/", []),
            ("P6.9", "特商法表示", "/tokushoho/", []),
            ("P6.10", "勤怠打刻(認証不要)", "/attendance/stamp/", [], 400),  # Requires QR params
            ("P6.11", "QR入荷ページ", "/stock/inbound/", []),
        ]
        for item in pages:
            tid, name, path, keywords = item[0], item[1], item[2], item[3]
            expected_status = item[4] if len(item) > 4 else 200
            try:
                status = self.goto(path)
                text = self.body_text()
                ss = self.screenshot(tid)
                found = [kw for kw in keywords if kw in text]
                missing = [kw for kw in keywords if kw not in text]
                ok = status == expected_status and not missing
                notes = f"Status:{status}"
                if missing:
                    notes += f", Missing:{missing}"
                self.add_result(tid, f"公開: {name}", "PASS" if ok else "FAIL", notes, ss)
            except Exception as e:
                self.add_result(tid, f"公開: {name}", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 7: ALL Admin Pages (Owner = full access)
    # ═══════════════════════════════════════════
    def phase7_admin_pages(self):
        print("\n=== Phase 7: All Admin Pages ===")
        if "owner" not in self._sessions:
            self.add_result("P7.0", "Admin pages", "SKIP", "No owner session")
            return

        pages = [
            ("P7.1", "Admin Home", "/admin/"),
            ("P7.2", "売上ダッシュボード", "/admin/dashboard/sales/"),
            ("P7.3", "旧ダッシュボードパス", "/admin/dashboard/restaurant/"),
            ("P7.4", "シフトカレンダー", "/admin/shift/calendar/"),
            ("P7.5", "本日のシフト", "/admin/shift/today/"),
            ("P7.6", "勤怠QR", "/admin/attendance/qr/"),
            ("P7.7", "勤怠PIN", "/admin/attendance/pin/"),
            ("P7.8", "勤怠ボード", "/admin/attendance/board/"),
            ("P7.9", "勤務実績", "/admin/attendance/performance/"),
            ("P7.10", "POS", "/admin/pos/"),
            ("P7.11", "キッチンディスプレイ", "/admin/pos/kitchen/"),
            ("P7.12", "来客分析", "/admin/analytics/visitors/"),
            ("P7.13", "AI推薦", "/admin/ai/recommendation/"),
            ("P7.14", "EC注文管理", "/admin/ec/orders/"),
            ("P7.15", "在庫ダッシュボード", "/admin/inventory/"),
            ("P7.16", "入荷登録", "/admin/inventory/stock-in/"),
            ("P7.17", "メニュープレビュー", "/admin/menu/preview/"),
            ("P7.18", "デバッグパネル", "/admin/debug/"),
            ("P7.19", "IoTセンサー", "/admin/iot/sensors/"),
            # Admin model pages
            ("P7.20", "スタッフ一覧", "/admin/booking/staff/"),
            ("P7.21", "給与期間", "/admin/booking/payrollperiod/"),
            ("P7.22", "シフト期間", "/admin/booking/shiftperiod/"),
            ("P7.23", "シフト希望", "/admin/booking/shiftrequest/"),
            ("P7.24", "シフト割当", "/admin/booking/shiftassignment/"),
            ("P7.25", "シフト公開履歴", "/admin/booking/shiftpublishhistory/"),
            ("P7.26", "店舗休業日", "/admin/booking/storecloseddate/"),
            ("P7.27", "予約一覧", "/admin/booking/schedule/"),
            ("P7.28", "商品一覧", "/admin/booking/product/"),
            ("P7.29", "カテゴリ一覧", "/admin/booking/category/"),
            ("P7.30", "物件一覧(admin)", "/admin/booking/property/"),
        ]

        self.use_session("owner")
        for tid, name, path in pages:
            try:
                status = self.goto(path)
                ss = self.screenshot(tid)
                # Menu preview redirects to /t/ so 302 is acceptable
                ok = status in (200, 301, 302)
                notes = f"Status:{status}, URL:{self._page.url.replace(BASE_URL, '')[:80]}"
                self.add_result(tid, f"Admin: {name}", "PASS" if ok else "FAIL", notes, ss)
            except Exception as e:
                self.add_result(tid, f"Admin: {name}", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 8: User-facing pages with login
    # ═══════════════════════════════════════════
    def phase8_user_pages(self):
        print("\n=== Phase 8: Authenticated User Pages ===")
        if "cast" not in self._sessions:
            self.add_result("P8.0", "User pages", "SKIP", "No cast session")
            return

        self.use_session("cast")
        pages = [
            ("P8.1", "マイページ", "/mypage/"),
            ("P8.2", "シフト一覧", "/shift/"),
            ("P8.3", "センサーダッシュボード", "/dashboard/sensors/"),
            ("P8.4", "MQ9グラフ", "/dashboard/mq9/"),
            ("P8.5", "物件一覧(公開)", "/properties/"),
            ("P8.6", "チェックインスキャン", "/checkin/"),
        ]
        for tid, name, path in pages:
            try:
                status = self.goto(path)
                ss = self.screenshot(tid)
                ok = status == 200
                notes = f"Status:{status}"
                self.add_result(tid, f"User: {name}", "PASS" if ok else "FAIL", notes, ss)
            except Exception as e:
                self.add_result(tid, f"User: {name}", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 9: EC Shop Flow (page-level)
    # ═══════════════════════════════════════════
    def phase9_ec_flow(self):
        print("\n=== Phase 9: EC Shop Flow ===")
        self._new_page()  # Anonymous user
        pages = [
            ("EC.1", "ショップトップ", "/shop/"),
            ("EC.2", "カート", "/shop/cart/"),
            ("EC.3", "チェックアウト", "/shop/checkout/"),
        ]
        for tid, name, path in pages:
            try:
                status = self.goto(path)
                text = self.body_text()
                ss = self.screenshot(tid)
                ok = status == 200
                notes = f"Status:{status}"
                self.add_result(tid, f"EC: {name}", "PASS" if ok else "FAIL", notes, ss)
            except Exception as e:
                self.add_result(tid, f"EC: {name}", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 10: Mobile Responsive
    # ═══════════════════════════════════════════
    def phase10_mobile(self):
        print("\n=== Phase 10: Mobile Responsive ===")
        viewports = [
            ("mobile", {"width": 375, "height": 812}),
            ("tablet", {"width": 768, "height": 1024}),
        ]
        key_pages = [
            ("/", "トップ"),
            ("/stores/", "店舗"),
            ("/shop/", "ショップ"),
            ("/news/", "ニュース"),
        ]

        for vp_name, vp in viewports:
            self._new_page(viewport=vp)
            for path, label in key_pages:
                tid = f"M.{vp_name[:3]}.{label}"
                try:
                    status = self.goto(path)
                    ss = self.screenshot(f"responsive_{vp_name}_{label}")
                    ok = status == 200
                    self.add_result(tid, f"{vp_name}: {label}",
                                    "PASS" if ok else "FAIL",
                                    f"Status:{status}, Viewport:{vp['width']}x{vp['height']}", ss)
                except Exception as e:
                    self.add_result(tid, f"{vp_name}: {label}", "FAIL", str(e)[:200])
            self._close_current()

        # Mobile admin pages
        if "manager" in self._sessions:
            self.use_session("manager", viewport={"width": 375, "height": 812})
            for path, label in [
                ("/admin/", "Admin Home"),
                ("/admin/dashboard/sales/", "ダッシュボード"),
                ("/admin/pos/", "POS"),
                ("/admin/shift/calendar/", "シフト"),
            ]:
                tid = f"M.mob.{label}"
                try:
                    status = self.goto(path)
                    ss = self.screenshot(f"responsive_mobile_admin_{label}")
                    ok = status == 200
                    self.add_result(tid, f"mobile-admin: {label}",
                                    "PASS" if ok else "FAIL",
                                    f"Status:{status}, Viewport:375x812", ss)
                except Exception as e:
                    self.add_result(tid, f"mobile-admin: {label}", "FAIL", str(e)[:200])
            self._close_current()

    # ═══════════════════════════════════════════
    # Phase 11: CSRF Token Validation
    # ═══════════════════════════════════════════
    def phase11_csrf(self):
        print("\n=== Phase 11: CSRF Token Validation ===")
        if "owner" not in self._sessions:
            self.add_result("CSRF.0", "CSRF validation", "SKIP", "No owner session")
            return

        self.use_session("owner")
        form_pages = [
            ("CSRF.1", "ログインフォーム", "/login/"),
            ("CSRF.2", "在庫入荷フォーム", "/admin/inventory/"),
            ("CSRF.3", "勤怠PINフォーム", "/admin/attendance/pin/"),
            ("CSRF.4", "勤怠QRフォーム", "/admin/attendance/qr/"),
        ]

        for tid, name, path in form_pages:
            try:
                self.goto(path)
                html = self.page_html()
                has_csrf = "csrfmiddlewaretoken" in html or "csrf_token" in html
                has_form = "<form" in html
                notes = f"Form:{has_form}, CSRF:{has_csrf}"
                if has_form:
                    ok = has_csrf
                else:
                    ok = True  # No form = no CSRF needed
                    notes += " (no form on page)"
                self.add_result(tid, f"CSRF: {name}", "PASS" if ok else "FAIL", notes)
            except Exception as e:
                self.add_result(tid, f"CSRF: {name}", "FAIL", str(e)[:200])

        # Check public form
        self._close_current()
        self._new_page()
        try:
            self.goto("/attendance/stamp/")
            html = self.page_html()
            has_csrf = "csrfmiddlewaretoken" in html or "csrf_token" in html or "X-CSRFToken" in html
            has_form = "<form" in html
            notes = f"Form:{has_form}, CSRF:{has_csrf}"
            ok = has_form and has_csrf if has_form else True
            self.add_result("CSRF.5", "CSRF: 勤怠打刻(公開)", "PASS" if ok else "FAIL", notes)
        except Exception as e:
            self.add_result("CSRF.5", "CSRF: 勤怠打刻(公開)", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 12: Dashboard API Smoke Tests (GET only)
    # ═══════════════════════════════════════════
    def phase12_apis(self):
        print("\n=== Phase 12: API Smoke Tests ===")
        if "manager" not in self._sessions:
            self.add_result("API.0", "API tests", "SKIP", "No manager session")
            return

        # Dashboard APIs (require login)
        dashboard_apis = [
            ("API.1", "売上統計", "/api/dashboard/sales/"),
            ("API.2", "予約統計", "/api/dashboard/reservations/"),
            ("API.3", "スタッフ実績", "/api/dashboard/staff-performance/"),
            ("API.4", "シフトサマリー", "/api/dashboard/shift-summary/"),
            ("API.5", "低在庫アラート", "/api/dashboard/low-stock/"),
            ("API.6", "メニュー工学", "/api/dashboard/menu-engineering/"),
            ("API.7", "ABC分析", "/api/dashboard/abc-analysis/"),
            ("API.8", "売上予測", "/api/dashboard/forecast/"),
            ("API.9", "KPIスコア", "/api/dashboard/kpi-scorecard/"),
            ("API.10", "NPS統計", "/api/dashboard/nps/"),
            ("API.11", "来客予測", "/api/dashboard/visitor-forecast/"),
            ("API.12", "CLV分析", "/api/dashboard/clv/"),
            ("API.13", "ヒートマップ", "/api/dashboard/sales-heatmap/"),
            ("API.14", "AOVトレンド", "/api/dashboard/aov-trend/"),
            ("API.15", "コホート分析", "/api/dashboard/cohort/"),
            ("API.16", "RFM分析", "/api/dashboard/rfm/"),
            ("API.17", "バスケット分析", "/api/dashboard/basket/"),
            ("API.18", "インサイト", "/api/dashboard/insights/"),
            ("API.19", "フィードバック", "/api/dashboard/feedback/"),
            ("API.20", "自動発注", "/api/dashboard/auto-order/"),
            ("API.21", "チャネル別売上", "/api/dashboard/channel-sales/"),
            ("API.22", "チェックイン統計", "/api/dashboard/checkin-stats/"),
            ("API.23", "レイアウト", "/api/dashboard/layout/"),
            ("API.24", "分析テキスト", "/api/dashboard/analysis-text/", 400),  # Requires POST body
            ("API.25", "外部データ", "/api/dashboard/external-data/"),
        ]

        self.use_session("manager")
        self.goto("/admin/")
        self._wait(1)

        for item in dashboard_apis:
            tid, name, path = item[0], item[1], item[2]
            expected = item[3] if len(item) > 3 else 200
            try:
                result = self._page.evaluate(f"""async () => {{
                    try {{
                        const resp = await fetch('{BASE_URL}{path}', {{
                            credentials: 'same-origin',
                            headers: {{'Accept': 'application/json'}},
                        }});
                        const text = await resp.text();
                        let isJson = false;
                        try {{ JSON.parse(text); isJson = true; }} catch {{}}
                        return {{status: resp.status, isJson, len: text.length}};
                    }} catch(e) {{
                        return {{status: 0, error: e.message}};
                    }}
                }}""")
                status = result.get("status", 0)
                is_json = result.get("isJson", False)
                ok = status == expected
                notes = f"Status:{status}, JSON:{is_json}, Size:{result.get('len', 0)}"
                if result.get("error"):
                    notes = f"Error:{result['error'][:80]}"
                self.add_result(tid, f"API: {name}", "PASS" if ok else "FAIL", notes)
            except Exception as e:
                self.add_result(tid, f"API: {name}", "FAIL", str(e)[:200])
        self._close_current()

        # Attendance APIs (require owner)
        if "owner" in self._sessions:
            self._wait(2)
            self.use_session("owner")
            self.goto("/admin/")
            self._wait(1)

            att_apis = [
                ("API.30", "勤怠日状態", "/api/attendance/day-status/"),
                ("API.31", "勤怠日状態HTML", "/api/attendance/day-status-html/"),
                ("API.32", "勤怠実績", "/api/attendance/performance/"),
            ]
            for tid, name, path in att_apis:
                try:
                    result = self._page.evaluate(f"""async () => {{
                        try {{
                            const resp = await fetch('{BASE_URL}{path}', {{
                                credentials: 'same-origin',
                            }});
                            return {{status: resp.status}};
                        }} catch(e) {{
                            return {{status: 0, error: e.message}};
                        }}
                    }}""")
                    status = result.get("status", 0)
                    ok = status == 200
                    self.add_result(tid, f"API: {name}", "PASS" if ok else "FAIL",
                                    f"Status:{status}")
                except Exception as e:
                    self.add_result(tid, f"API: {name}", "FAIL", str(e)[:200])
            self._close_current()

        # Analytics APIs
        if "manager" in self._sessions:
            self._wait(2)
            self.use_session("manager")
            self.goto("/admin/")
            self._wait(1)

            analytics_apis = [
                ("API.40", "来客カウント", "/api/analytics/visitors/"),
                ("API.41", "来客ヒートマップ", "/api/analytics/heatmap/"),
                ("API.42", "コンバージョン", "/api/analytics/conversion/"),
                ("API.43", "EC注文一覧", "/api/ec/orders/"),
                ("API.44", "AIモデル状態", "/api/ai/model-status/"),
                ("API.45", "メニューJSON", "/api/menu", 400),  # Requires store_id param
            ]
            for item in analytics_apis:
                tid, name, path = item[0], item[1], item[2]
                expected = item[3] if len(item) > 3 else 200
                try:
                    result = self._page.evaluate(f"""async () => {{
                        try {{
                            const resp = await fetch('{BASE_URL}{path}', {{
                                credentials: 'same-origin',
                                headers: {{'Accept': 'application/json'}},
                            }});
                            return {{status: resp.status}};
                        }} catch(e) {{
                            return {{status: 0, error: e.message}};
                        }}
                    }}""")
                    status = result.get("status", 0)
                    ok = status == expected
                    self.add_result(tid, f"API: {name}", "PASS" if ok else "FAIL",
                                    f"Status:{status}")
                except Exception as e:
                    self.add_result(tid, f"API: {name}", "FAIL", str(e)[:200])
            self._close_current()

        # Unauthenticated API tests (should be 401/403)
        self._wait(2)
        self._new_page()
        self.goto("/")
        self._wait(1)
        unauth_apis = [
            ("API.50", "未認証: 売上API", "/api/dashboard/sales/", [401, 403, 302]),
            ("API.51", "未認証: EC注文API", "/api/ec/orders/", [401, 403, 302]),
            ("API.52", "未認証: デバッグAPI", "/api/debug/panel/", [401, 403, 302]),
        ]
        for tid, name, path, expected in unauth_apis:
            try:
                result = self._page.evaluate(f"""async () => {{
                    try {{
                        const resp = await fetch('{BASE_URL}{path}', {{
                            credentials: 'same-origin',
                            redirect: 'manual',
                        }});
                        return {{status: resp.status, type: resp.type}};
                    }} catch(e) {{
                        return {{status: 0, error: e.message}};
                    }}
                }}""")
                status = result.get("status", 0)
                resp_type = result.get("type", "")
                # opaqueredirect means 302 which is correct
                ok = status in expected or resp_type == "opaqueredirect"
                notes = f"Status:{status}, Type:{resp_type}"
                self.add_result(tid, f"API: {name}", "PASS" if ok else "FAIL", notes)
            except Exception as e:
                self.add_result(tid, f"API: {name}", "FAIL", str(e)[:200])
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 13: Table QR Ordering (need UUID)
    # ═══════════════════════════════════════════
    def phase13_table_qr(self):
        print("\n=== Phase 13: Table QR Ordering ===")
        if "owner" not in self._sessions:
            self.add_result("QR.0", "Table QR", "SKIP", "No owner session")
            return

        # First, find a table UUID from the menu preview redirect
        self.use_session("owner")
        try:
            self.goto("/admin/menu/preview/")
            time.sleep(2)
            url = self._page.url
            # URL should redirect to /t/<uuid>/
            if "/t/" in url:
                import re
                match = re.search(r'/t/([a-f0-9-]+)/', url)
                if match:
                    table_uuid = match.group(1)
                    self._close_current()
                    self._new_page()  # Anonymous context for table ordering

                    table_pages = [
                        ("QR.1", "テーブルメニュー", f"/t/{table_uuid}/"),
                        ("QR.2", "テーブルカート", f"/t/{table_uuid}/cart/"),
                        ("QR.3", "テーブル注文履歴", f"/t/{table_uuid}/history/"),
                    ]
                    for tid, name, path in table_pages:
                        try:
                            status = self.goto(path)
                            ss = self.screenshot(tid)
                            ok = status == 200
                            self.add_result(tid, f"QR: {name}", "PASS" if ok else "FAIL",
                                            f"Status:{status}", ss)
                        except Exception as e:
                            self.add_result(tid, f"QR: {name}", "FAIL", str(e)[:200])
                    self._close_current()
                    return

            self.add_result("QR.0", "Table QR", "SKIP", f"No table UUID found (URL: {url[:80]})")
        except Exception as e:
            self.add_result("QR.0", "Table QR", "SKIP", f"Error finding table: {str(e)[:100]}")
        self._close_current()

    # ═══════════════════════════════════════════
    # Phase 14: i18n All Pages (zh-hant)
    # ═══════════════════════════════════════════
    def phase14_i18n(self):
        print("\n=== Phase 14: i18n All Pages (zh-hant) ===")
        self._new_page()
        pages = [
            ("I18.1", "トップ", "/zh-hant/"),
            ("I18.2", "店舗", "/zh-hant/stores/"),
            ("I18.3", "占い師", "/zh-hant/fortune-tellers/"),
            ("I18.4", "カレンダー", "/zh-hant/date-calendar/"),
            ("I18.5", "ショップ", "/zh-hant/shop/"),
            ("I18.6", "ニュース", "/zh-hant/news/"),
            ("I18.7", "ヘルプ", "/zh-hant/help/"),
            ("I18.8", "プライバシー", "/zh-hant/privacy/"),
            ("I18.9", "特商法", "/zh-hant/tokushoho/"),
        ]
        for tid, name, path in pages:
            try:
                status = self.goto(path)
                url = self._page.url
                ss = self.screenshot(tid)
                has_prefix = "/zh-hant/" in url
                ok = status == 200 and has_prefix
                self.add_result(tid, f"i18n: {name}", "PASS" if ok else "FAIL",
                                f"Status:{status}, ZH:{has_prefix}", ss)
            except Exception as e:
                self.add_result(tid, f"i18n: {name}", "FAIL", str(e)[:200])
        self._close_current()

        # i18n admin pages
        if "manager" in self._sessions:
            self.use_session("manager")
            admin_pages = [
                ("I18.10", "Admin Home", "/zh-hant/admin/"),
                ("I18.11", "ダッシュボード", "/zh-hant/admin/dashboard/sales/"),
                ("I18.12", "POS", "/zh-hant/admin/pos/"),
                ("I18.13", "シフト", "/zh-hant/admin/shift/calendar/"),
                ("I18.14", "在庫", "/zh-hant/admin/inventory/"),
                ("I18.15", "EC注文", "/zh-hant/admin/ec/orders/"),
            ]
            for tid, name, path in admin_pages:
                try:
                    status = self.goto(path)
                    url = self._page.url
                    ss = self.screenshot(tid)
                    has_prefix = "/zh-hant/" in url
                    ok = status == 200 and has_prefix
                    self.add_result(tid, f"i18n-admin: {name}", "PASS" if ok else "FAIL",
                                    f"Status:{status}, ZH:{has_prefix}", ss)
                except Exception as e:
                    self.add_result(tid, f"i18n-admin: {name}", "FAIL", str(e)[:200])
            self._close_current()

    # ═══════════════════════════════════════════
    # Phase 15: Network Error Sweep
    # ═══════════════════════════════════════════
    def phase15_network_sweep(self):
        print("\n=== Phase 15: Network Error Sweep ===")
        if "owner" not in self._sessions:
            self.add_result("NET.0", "Network sweep", "SKIP", "No owner session")
            return

        self.use_session("owner")
        heavy_pages = [
            ("NET.1", "ダッシュボード", "/admin/dashboard/sales/"),
            ("NET.2", "POS", "/admin/pos/"),
            ("NET.3", "在庫", "/admin/inventory/"),
            ("NET.4", "シフト", "/admin/shift/calendar/"),
            ("NET.5", "トップ(公開)", "/"),
        ]
        all_net_errors = []
        for tid, name, path in heavy_pages:
            try:
                self._network_errors = []
                self.goto(path)
                time.sleep(3)  # Wait for all assets to load
                net_errors = self.get_network_errors()
                all_net_errors.extend(net_errors)
                ok = len(net_errors) == 0
                if net_errors:
                    err_summary = "; ".join(f"{e['status']}:{e['url'][-50:]}" for e in net_errors[:3])
                    notes = f"Errors:{len(net_errors)} [{err_summary}]"
                else:
                    notes = "No network errors"
                self.add_result(tid, f"NET: {name}", "PASS" if ok else "FAIL", notes)
            except Exception as e:
                self.add_result(tid, f"NET: {name}", "FAIL", str(e)[:200])
        self._close_current()

        # Summary
        if all_net_errors:
            unique = set(f"{e['status']}:{e['url']}" for e in all_net_errors)
            print(f"  Total unique network errors: {len(unique)}")
            for u in list(unique)[:5]:
                print(f"    {u[:120]}")

    # ═══════════════════════════════════════════
    # Phase 16: Legacy Redirects & Edge Cases
    # ═══════════════════════════════════════════
    def phase16_edge_cases(self):
        print("\n=== Phase 16: Edge Cases ===")
        self._new_page()

        # Legacy URLs
        legacy = [
            ("EDGE.1", "旧prebooking", "/staff/10/prebooking/2024/4/29/14/list_clinic.html"),
            ("EDGE.2", "旧MQ9", "/booking/mq9/"),
        ]
        for tid, name, path in legacy:
            try:
                status = self.goto(path)
                url = self._page.url
                # Should redirect to home
                ok = status == 200  # After following 301, lands on 200
                self.add_result(tid, f"Legacy: {name}", "PASS" if ok else "FAIL",
                                f"Landed:{url.replace(BASE_URL, '')[:60]}")
            except Exception as e:
                self.add_result(tid, f"Legacy: {name}", "FAIL", str(e)[:200])

        # 404 page
        try:
            status = self.goto("/nonexistent-page-xyz/")
            ss = self.screenshot("EDGE.3")
            ok = status == 404
            self.add_result("EDGE.3", "404ページ", "PASS" if ok else "FAIL",
                            f"Status:{status}", ss)
        except Exception as e:
            self.add_result("EDGE.3", "404ページ", "FAIL", str(e)[:200])

        # Health check
        try:
            status = self.goto("/healthz")
            text = self.body_text()
            ok = status == 200 and "ok" in text.lower()
            self.add_result("EDGE.4", "ヘルスチェック", "PASS" if ok else "FAIL",
                            f"Status:{status}, Body:{text[:50]}")
        except Exception as e:
            self.add_result("EDGE.4", "ヘルスチェック", "FAIL", str(e)[:200])

        self._close_current()

    # ═══════════════════════════════════════════
    # Report
    # ═══════════════════════════════════════════
    def generate_report(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")

        # Group by phase
        phases = {}
        for r in self.results:
            prefix = r.test_id.split(".")[0]
            phase_map = {
                "P6": "Phase 6: 全公開ページ",
                "P7": "Phase 7: 全管理ページ",
                "P8": "Phase 8: ユーザーページ",
                "EC": "Phase 9: ECフロー",
                "M": "Phase 10: モバイル",
                "CSRF": "Phase 11: CSRF検証",
                "API": "Phase 12: API",
                "QR": "Phase 13: QR注文",
                "I18": "Phase 14: i18n",
                "NET": "Phase 15: ネットワーク",
                "EDGE": "Phase 16: エッジケース",
            }
            phase_name = phase_map.get(prefix, f"Other ({prefix})")
            phases.setdefault(phase_name, []).append(r)

        lines = [
            "# 包括的 E2E テスト結果 — timebaibai.com", "",
            f"日時: {now}",
            "テスター: Playwright (headless Chromium)",
            "環境: 本番 (https://timebaibai.com)", "",
            "## サマリー", "",
            f"**合計: {total} テスト | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}**", "",
            "| Phase | テスト数 | PASS | FAIL | SKIP |",
            "|---|---|---|---|---|",
        ]

        for pname, pr in phases.items():
            n = len(pr)
            p = sum(1 for r in pr if r.status == "PASS")
            f = sum(1 for r in pr if r.status == "FAIL")
            s = sum(1 for r in pr if r.status == "SKIP")
            lines.append(f"| {pname} | {n} | {p} | {f} | {s} |")

        lines += ["", "## 詳細結果", "",
                   "| ID | テスト名 | 結果 | 備考 |",
                   "|---|---|---|---|"]
        for r in self.results:
            notes = r.notes.replace("|", "\\|")[:120]
            if r.js_errors:
                notes += f" [JS:{len(r.js_errors)}]"
            if r.network_errors:
                notes += f" [NET:{len(r.network_errors)}]"
            lines.append(f"| {r.test_id} | {r.name} | {r.status} | {notes} |")

        # Failures detail
        fails = [r for r in self.results if r.status == "FAIL"]
        if fails:
            lines += ["", "## 失敗テスト詳細", ""]
            for r in fails:
                lines.append(f"### {r.test_id}: {r.name}")
                lines.append(f"- 備考: {r.notes}")
                if r.js_errors:
                    lines.append(f"- JSエラー: {r.js_errors[:3]}")
                if r.network_errors:
                    lines.append(f"- ネットワークエラー: {r.network_errors[:3]}")
                lines.append("")

        return "\n".join(lines)

    def run_all(self):
        print(f"Comprehensive E2E Test — {BASE_URL}")
        self.start()
        try:
            # Health check
            p = self._new_page()
            resp = p.goto(f"{BASE_URL}/healthz", timeout=15000)
            print(f"Health: {resp.status if resp else 'N/A'}")
            self._close_current()

            # Login all roles
            print("\n=== Login Sessions ===")
            for role in ["cast", "staff", "manager", "owner"]:
                try:
                    ok = self.do_login(role)
                    print(f"  {role}: {'OK' if ok else 'FAILED'}")
                    self._wait(18)
                except Exception as e:
                    print(f"  {role}: ERROR - {str(e)[:80]}")
                    self._wait(18)

            # Run all phases
            self.phase6_public_pages()
            self.phase7_admin_pages()
            self.phase8_user_pages()
            self.phase9_ec_flow()
            self.phase10_mobile()
            self.phase11_csrf()
            self.phase12_apis()
            self.phase13_table_qr()
            self.phase14_i18n()
            self.phase15_network_sweep()
            self.phase16_edge_cases()
        finally:
            self.stop()

        # Save report
        report = self.generate_report()
        report_path = os.path.join(SCREENSHOT_DIR, "COMPREHENSIVE_REPORT.md")
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport: {report_path}")

        # JSON results
        json_path = os.path.join(SCREENSHOT_DIR, "results.json")
        with open(json_path, "w") as f:
            json.dump([{
                "test_id": r.test_id, "name": r.name, "status": r.status,
                "notes": r.notes, "js_errors": r.js_errors,
                "network_errors": r.network_errors,
            } for r in self.results], f, ensure_ascii=False, indent=2)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        skipped = sum(1 for r in self.results if r.status == "SKIP")
        print(f"\n{'='*60}")
        print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed} | SKIP: {skipped}")
        print(f"{'='*60}")
        return failed == 0


if __name__ == "__main__":
    runner = ComprehensiveE2ERunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
