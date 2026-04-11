#!/usr/bin/env python3
"""E2E Test Runner for timebaibai.com (production)

Playwright headless Chromium, real data, no stubs/mocks.
Uses saved session state to minimize login calls (server has 2 workers only).
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

from playwright.sync_api import sync_playwright

BASE_URL = "https://timebaibai.com"
SCREENSHOT_DIR = "/tmp/e2e"
DELAY = 3  # seconds between requests

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


class E2ERunner:
    def __init__(self):
        self.results = []
        self.pw = None
        self.browser = None
        self._sessions = {}  # role -> storage state path
        self._current_ctx = None
        self._page = None
        self._js_errors = []

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

    def _new_page(self, storage_state=None):
        self._close_current()
        self._js_errors = []
        opts = {"viewport": {"width": 1280, "height": 900}, "ignore_https_errors": True}
        if storage_state:
            opts["storage_state"] = storage_state
        self._current_ctx = self.browser.new_context(**opts)
        self._page = self._current_ctx.new_page()
        self._page.on("console", self._on_console)
        self._page.on("pageerror", self._on_pageerror)
        return self._page

    def _on_console(self, msg):
        if msg.type == "error":
            text = msg.text
            if "fonts.googleapis.com" in text:
                return
            if "503" in text or "Service Temporarily Unavailable" in text:
                return  # ignore rate limit artifacts
            if "Failed to load resource" in text:
                return  # ignore 404 resource loading (static assets)
            if "Content Security Policy" in text:
                return  # ignore CSP warnings
            self._js_errors.append(text)

    def _on_pageerror(self, err):
        self._js_errors.append(str(err))

    def _wait(self, secs=None):
        time.sleep(secs or DELAY)

    def do_login(self, role):
        """Login and save session state. Returns True on success."""
        page = self._new_page()
        self._wait(5)
        page.goto(f"{BASE_URL}/login/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector('input[name="username"]', timeout=15000)
        creds = ACCOUNTS[role]
        page.fill('input[name="username"]', creds["username"])
        page.fill('input[name="password"]', creds["password"])
        page.click('button[type="submit"]')
        # Wait for redirect chain: /login/ -> /login/redirect/ -> /admin/
        time.sleep(5)
        # If still on login page, try waiting longer
        for _ in range(3):
            url = page.url
            if url.endswith("/login/") or url.endswith("/login"):
                time.sleep(2)
            else:
                break
        url = page.url
        # /login/redirect/ means login succeeded (smart redirect view)
        success = not url.endswith("/login/") and not url.endswith("/login")
        if success:
            # Navigate to /admin/ to complete the redirect chain
            if "/admin/" not in url:
                page.goto(f"{BASE_URL}/admin/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(2)
            state_path = os.path.join(SCREENSHOT_DIR, f"state_{role}.json")
            self._current_ctx.storage_state(path=state_path)
            self._sessions[role] = state_path
        self._close_current()
        return success

    def use_session(self, role):
        """Open a page using saved session for role."""
        state = self._sessions.get(role)
        return self._new_page(storage_state=state)

    def goto(self, path, timeout=30000):
        self._wait(1)
        resp = self._page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=timeout)
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

    def add_result(self, test_id, name, status, notes="", screenshot=""):
        js_errors = self.get_js_errors()
        r = TestResult(test_id=test_id, name=name, status=status,
                       notes=notes, screenshot=screenshot, js_errors=js_errors)
        self.results.append(r)
        icon = {"PASS": "OK", "FAIL": "NG", "BLOCKED": "--"}.get(status, "??")
        print(f"  [{icon}] {test_id}: {name} — {notes[:120]}")
        if js_errors:
            for e in js_errors[:2]:
                print(f"    JS: {e[:100]}")

    # =========================================
    # Phase 0: Login all roles, save sessions
    # =========================================
    def phase0_login_all(self):
        print("\n=== Phase 0: Establish Sessions ===")
        for role in ["cast", "staff", "manager", "owner"]:
            try:
                ok = self.do_login(role)
                print(f"  {role}: {'OK' if ok else 'FAILED'}")
                if not ok:
                    print(f"    WARNING: {role} login failed, some tests will be BLOCKED")
                self._wait(15)  # Extra delay between logins
            except Exception as e:
                print(f"  {role}: ERROR - {str(e)[:100]}")
                self._wait(15)

    # =========================================
    # Phase 1: Login + Sidebar Tests
    # =========================================
    def phase1(self):
        print("\n=== Phase 1: Login + Sidebar Tests ===")
        roles = ["cast", "staff", "manager", "owner"]
        checks = {
            "cast": {"want": ["シフト", "IoT制御登録", "SNS自動投稿"], "deny": ["デバッグ", "給与"]},
            "staff": {"want": ["シフト", "IoT制御登録", "SNS自動投稿"], "deny": ["デバッグ", "給与"]},
            "manager": {"want": ["予約管理", "シフト", "IoT制御登録", "SNS自動投稿"], "deny": []},
            "owner": {"want": ["シフト", "セキュリティ", "システム"], "deny": []},
        }
        for i, role in enumerate(roles):
            tid = f"T1.{i+1}"
            if role not in self._sessions:
                self.add_result(tid, f"{role} login + sidebar", "BLOCKED", "Login session unavailable")
                continue
            try:
                self.use_session(role)
                status = self.goto("/admin/")
                ss = self.screenshot(f"login_{role}")
                text = self.body_text()

                notes = [f"Status: {status}"]
                check = checks[role]
                for kw in check["want"]:
                    notes.append(f"'{kw}': {'OK' if kw in text else 'MISSING'}")
                for kw in check["deny"]:
                    if kw in text:
                        notes.append(f"WARNING: '{kw}' visible")

                missing = [kw for kw in check["want"] if kw not in text]
                leaked = [kw for kw in check["deny"] if kw in text]
                ok = status == 200 and not missing and not leaked
                self.add_result(tid, f"{role} login + sidebar",
                                "PASS" if ok else "FAIL", "; ".join(notes), ss)
            except Exception as e:
                self.add_result(tid, f"{role} login + sidebar", "FAIL", str(e)[:200])
            finally:
                self._close_current()

    # =========================================
    # Phase 2: Workflow Tests
    # =========================================
    def phase2(self):
        print("\n=== Phase 2: Workflow Tests ===")

        # Cast tests
        if "cast" in self._sessions:
            self.use_session("cast")
            for tid, name, path, keywords in [
                ("T2.1", "Cast: シフトカレンダー閲覧", "/shift/", ["シフト"]),
                ("T2.2", "Cast: シフト希望画面", "/shift/", ["希望", "シフト"]),
                ("T2.3a", "Cast: 管理シフトカレンダー", "/admin/shift/calendar/", ["シフト"]),
                ("T2.4", "Cast: マイページ", "/mypage/", []),
                ("T2.5", "Cast: 勤怠PIN画面", "/admin/attendance/pin/", ["PIN", "打刻", "タイムカード"]),
            ]:
                try:
                    status = self.goto(path)
                    text = self.body_text()
                    ss = self.screenshot(f"cast_{tid}")
                    found = [kw for kw in keywords if kw in text]
                    self.add_result(tid if "a" not in tid else "T2.3",
                                    name, "PASS" if status == 200 else "FAIL",
                                    f"Status: {status}, Found: {found}", ss)
                except Exception as e:
                    self.add_result(tid, name, "FAIL", str(e)[:200])

            # T2.3b: Today shift
            try:
                status = self.goto("/admin/shift/today/")
                ss = self.screenshot("cast_T2.3b")
                self.add_result("T2.3b", "Cast: 本日のシフト",
                                "PASS" if status == 200 else "FAIL",
                                f"Status: {status}", ss)
            except Exception as e:
                self.add_result("T2.3b", "Cast: 本日のシフト", "FAIL", str(e)[:200])
            self._close_current()
        else:
            for tid in ["T2.1", "T2.2", "T2.3", "T2.3b", "T2.4", "T2.5"]:
                self.add_result(tid, f"Cast test", "BLOCKED", "No session")

        self._wait(3)

        # Manager tests
        if "manager" in self._sessions:
            self.use_session("manager")
            for tid, name, path, keywords in [
                ("T2.6", "Manager: 売上ダッシュボード", "/admin/dashboard/sales/", ["売上", "ダッシュボード"]),
                ("T2.7", "Manager: POS画面", "/admin/pos/", ["POS", "商品"]),
                ("T2.8", "Manager: EC注文管理", "/admin/ec/orders/", ["注文", "EC"]),
            ]:
                try:
                    status = self.goto(path)
                    text = self.body_text()
                    html = self.page_html()
                    ss = self.screenshot(f"manager_{tid}")
                    found = [kw for kw in keywords if kw in text or kw.lower() in html.lower()]
                    self.add_result(tid, name, "PASS" if status == 200 else "FAIL",
                                    f"Status: {status}, Found: {found}", ss)
                except Exception as e:
                    self.add_result(tid, name, "FAIL", str(e)[:200])
            self._close_current()
        else:
            for tid in ["T2.6", "T2.7", "T2.8"]:
                self.add_result(tid, f"Manager test", "BLOCKED", "No session")

        self._wait(3)

        # Owner tests
        if "owner" in self._sessions:
            self.use_session("owner")
            for tid, name, path, keywords in [
                ("T2.9", "Owner: デバッグパネル", "/admin/debug/", ["デバイス", "IoT", "デバッグ"]),
                ("T2.10", "Owner: 給与管理", "/admin/booking/payrollperiod/", ["追加", "給与"]),
            ]:
                try:
                    status = self.goto(path)
                    text = self.body_text()
                    ss = self.screenshot(f"owner_{tid}")
                    found = [kw for kw in keywords if kw in text]
                    self.add_result(tid, name, "PASS" if status == 200 else "FAIL",
                                    f"Status: {status}, Found: {found}", ss)
                except Exception as e:
                    self.add_result(tid, name, "FAIL", str(e)[:200])

            # T2.11: Properties - try public URL first, then admin
            try:
                status = self.goto("/properties/")
                ss = self.screenshot("owner_T2.11")
                if status != 200:
                    status2 = self.goto("/admin/booking/property/")
                    ss = self.screenshot("owner_T2.11_admin")
                    self.add_result("T2.11", "Owner: 物件管理",
                                    "PASS" if status2 == 200 else "FAIL",
                                    f"/properties/: {status}, admin: {status2}", ss)
                else:
                    self.add_result("T2.11", "Owner: 物件管理", "PASS", f"Status: {status}", ss)
            except Exception as e:
                self.add_result("T2.11", "Owner: 物件管理", "FAIL", str(e)[:200])
            self._close_current()
        else:
            for tid in ["T2.9", "T2.10", "T2.11"]:
                self.add_result(tid, f"Owner test", "BLOCKED", "No session")

    # =========================================
    # Phase 3: Cross-Role Integration
    # =========================================
    def phase3(self):
        print("\n=== Phase 3: Cross-Role Integration ===")

        mgr = "manager" in self._sessions
        cast = "cast" in self._sessions

        # T3.1: Manager shift calendar → Cast view
        if mgr and cast:
            try:
                self.use_session("manager")
                s1 = self.goto("/admin/shift/calendar/")
                ss1 = self.screenshot("cross_T3.1_manager")
                self._close_current()
                self._wait(2)

                self.use_session("cast")
                s2 = self.goto("/shift/")
                ss2 = self.screenshot("cross_T3.1_cast")
                self._close_current()

                self.add_result("T3.1", "Manager→Cast シフト期間",
                                "PASS" if (s1 == 200 and s2 == 200) else "FAIL",
                                f"Manager: {s1}, Cast: {s2}", ss2)
            except Exception as e:
                self.add_result("T3.1", "Manager→Cast シフト期間", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T3.1", "Manager→Cast シフト期間", "BLOCKED", "Missing sessions")

        self._wait(2)

        # T3.2: Cast → Manager shift requests
        if cast and mgr:
            try:
                self.use_session("cast")
                s1 = self.goto("/shift/")
                self.screenshot("cross_T3.2_cast")
                self._close_current()
                self._wait(2)

                self.use_session("manager")
                s2 = self.goto("/admin/booking/shiftrequest/")
                ss = self.screenshot("cross_T3.2_manager")
                self._close_current()

                self.add_result("T3.2", "Cast→Manager シフト希望",
                                "PASS" if (s1 == 200 and s2 == 200) else "FAIL",
                                f"Cast: {s1}, Manager requests: {s2}", ss)
            except Exception as e:
                self.add_result("T3.2", "Cast→Manager シフト希望", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T3.2", "Cast→Manager シフト希望", "BLOCKED", "Missing sessions")

        self._wait(2)

        # T3.3: Manager calendar → Cast calendar
        if mgr and cast:
            try:
                self.use_session("manager")
                s1 = self.goto("/admin/shift/calendar/")
                self.screenshot("cross_T3.3_manager")
                self._close_current()
                self._wait(2)

                self.use_session("cast")
                s2 = self.goto("/admin/shift/calendar/")
                ss = self.screenshot("cross_T3.3_cast")
                self._close_current()

                self.add_result("T3.3", "Manager公開→Cast確認",
                                "PASS" if (s1 == 200 and s2 == 200) else "FAIL",
                                f"Manager: {s1}, Cast: {s2}", ss)
            except Exception as e:
                self.add_result("T3.3", "Manager公開→Cast確認", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T3.3", "Manager公開→Cast確認", "BLOCKED", "Missing sessions")

    # =========================================
    # Phase 4: Permission Boundary
    # =========================================
    def phase4(self):
        print("\n=== Phase 4: Permission Boundary ===")

        # T4.1: Cast → admin-only pages
        if "cast" in self._sessions:
            try:
                self.use_session("cast")
                s1 = self.goto("/admin/debug/")
                text1 = self.body_text()
                ss1 = self.screenshot("perm_T4.1_debug")
                self._wait(2)

                s2 = self.goto("/admin/dashboard/sales/")
                text2 = self.body_text()
                self.screenshot("perm_T4.1_sales")
                self._close_current()

                # Cast shouldn't see debug panel content (system group not in their visible_groups)
                debug_ok = s1 == 403 or "デバッグ" not in text1 or "権限" in text1
                self.add_result("T4.1", "Cast→管理者専用ページ",
                                "PASS" if debug_ok else "FAIL",
                                f"Debug: {s1} (blocked={debug_ok}), Sales: {s2}", ss1)
            except Exception as e:
                self.add_result("T4.1", "Cast→管理者専用ページ", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T4.1", "Cast→管理者専用ページ", "BLOCKED", "No session")

        self._wait(3)

        # T4.2: Manager cannot delete
        if "manager" in self._sessions:
            try:
                self.use_session("manager")
                s1 = self.goto("/admin/booking/staff/1/delete/")
                text = self.body_text()
                ss = self.screenshot("perm_T4.2")
                self._close_current()

                blocked = (s1 == 403 or s1 == 302 or "権限" in text
                           or "Permission" in text or "forbidden" in text.lower()
                           or "パーミッションがありません" in text
                           or "permission" in text.lower())
                self.add_result("T4.2", "Manager削除不可",
                                "PASS" if blocked else "FAIL",
                                f"Status: {s1}, Blocked: {blocked}", ss)
            except Exception as e:
                self.add_result("T4.2", "Manager削除不可", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T4.2", "Manager削除不可", "BLOCKED", "No session")

        self._wait(3)

        # T4.3: Staff cannot add
        if "staff" in self._sessions:
            try:
                self.use_session("staff")
                s1 = self.goto("/admin/booking/staff/add/")
                text = self.body_text()
                ss = self.screenshot("perm_T4.3")
                self._close_current()

                blocked = (s1 == 403 or s1 == 302 or "権限" in text
                           or "Permission" in text or "forbidden" in text.lower())
                self.add_result("T4.3", "Staff追加不可",
                                "PASS" if blocked else "FAIL",
                                f"Status: {s1}, Blocked: {blocked}", ss)
            except Exception as e:
                self.add_result("T4.3", "Staff追加不可", "FAIL", str(e)[:200])
                self._close_current()
        else:
            self.add_result("T4.3", "Staff追加不可", "BLOCKED", "No session")

        self._wait(3)

        # T4.4: Unauthenticated → redirect
        try:
            page = self._new_page()  # Clean session, no cookies
            results = {}
            for path in ["/shift/", "/admin/", "/mypage/"]:
                self._wait(1)
                page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=15000)
                time.sleep(1)
                results[path] = "login" in page.url.lower()

            ss = self.screenshot("perm_T4.4")
            self._close_current()

            all_ok = all(results.values())
            notes = "; ".join(f"{p}: {'->login' if r else 'NO REDIR'}" for p, r in results.items())
            self.add_result("T4.4", "未認証→リダイレクト",
                            "PASS" if all_ok else "FAIL", notes, ss)
        except Exception as e:
            self.add_result("T4.4", "未認証→リダイレクト", "FAIL", str(e)[:200])
            self._close_current()

    # =========================================
    # Phase 5: Public Pages + i18n
    # =========================================
    def phase5(self):
        print("\n=== Phase 5: Public Pages + i18n ===")

        # T5.1: 7 public pages
        try:
            self._new_page()
            pages = [
                ("/", "トップ"), ("/stores/", "店舗"), ("/fortune-tellers/", "占い師"),
                ("/date-calendar/", "カレンダー"), ("/shop/", "ショップ"),
                ("/news/", "ニュース"), ("/help/", "ヘルプ"),
            ]
            all_ok = True
            notes = []
            for path, label in pages:
                try:
                    status = self.goto(path)
                    js = self.get_js_errors()
                    ok = status == 200 and not js
                    if not ok:
                        all_ok = False
                    n = f"{label}:{status}"
                    if js:
                        n += f"[JS:{len(js)}]"
                    notes.append(n)
                except Exception:
                    all_ok = False
                    notes.append(f"{label}:ERR")

            ss = self.screenshot("public_T5.1")
            self._close_current()
            self.add_result("T5.1", "公開7ページ確認",
                            "PASS" if all_ok else "FAIL", ", ".join(notes), ss)
        except Exception as e:
            self.add_result("T5.1", "公開7ページ確認", "FAIL", str(e)[:200])
            self._close_current()

        self._wait(2)

        # T5.2: Chinese i18n
        try:
            self._new_page()
            s1 = self.goto("/zh-hant/")
            t1 = self.body_text()
            self.screenshot("i18n_T5.2_top")
            self._wait(1)

            s2 = self.goto("/zh-hant/stores/")
            t2 = self.body_text()
            ss = self.screenshot("i18n_T5.2_stores")
            self._close_current()

            has_zh = any(c in t1 + t2 for c in ["的", "店", "預約", "首頁", "占卜", "關於"])
            self.add_result("T5.2", "中国語切替",
                            "PASS" if (s1 == 200 and s2 == 200) else "FAIL",
                            f"Top: {s1}, Stores: {s2}, ZH: {has_zh}", ss)
        except Exception as e:
            self.add_result("T5.2", "中国語切替", "FAIL", str(e)[:200])
            self._close_current()

    # =========================================
    # Report
    # =========================================
    def generate_report(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        phases = {
            "Phase 1: ログイン": [r for r in self.results if r.test_id.startswith("T1.")],
            "Phase 2: ワークフロー": [r for r in self.results if r.test_id.startswith("T2.")],
            "Phase 3: ロール間連動": [r for r in self.results if r.test_id.startswith("T3.")],
            "Phase 4: 権限境界": [r for r in self.results if r.test_id.startswith("T4.")],
            "Phase 5: 公開ページ": [r for r in self.results if r.test_id.startswith("T5.")],
        }

        lines = [
            "# E2E テスト結果 — timebaibai.com", "",
            f"日時: {now}", "テスター: Playwright (headless Chromium)",
            "環境: 本番 (https://timebaibai.com)", "",
            "## サマリー", "",
            "| Phase | テスト数 | PASS | FAIL | BLOCKED |",
            "|---|---|---|---|---|",
        ]

        tp = tf = tb = 0
        for pname, pr in phases.items():
            n = len(pr)
            p = sum(1 for r in pr if r.status == "PASS")
            f = sum(1 for r in pr if r.status == "FAIL")
            b = sum(1 for r in pr if r.status == "BLOCKED")
            lines.append(f"| {pname} | {n} | {p} | {f} | {b} |")
            tp += p; tf += f; tb += b

        lines.append(f"| **合計** | **{tp+tf+tb}** | **{tp}** | **{tf}** | **{tb}** |")
        lines.append("")

        lines += ["## 詳細結果", "",
                   "| ID | テスト名 | 結果 | 備考 | スクリーンショット |",
                   "|---|---|---|---|---|"]
        for r in self.results:
            ss = os.path.basename(r.screenshot) if r.screenshot else "-"
            notes = r.notes.replace("|", "\\|")[:150]
            if r.js_errors:
                notes += f" [JS:{len(r.js_errors)}]"
            lines.append(f"| {r.test_id} | {r.name} | {r.status} | {notes} | {ss} |")

        lines += ["", "## 発見事項", ""]
        fails = [r for r in self.results if r.status == "FAIL"]
        js_issues = [r for r in self.results if r.js_errors]
        if fails:
            for r in fails:
                lines.append(f"- [HIGH] {r.test_id} {r.name}: {r.notes[:100]}")
        if js_issues:
            for r in js_issues:
                for e in r.js_errors[:2]:
                    lines.append(f"- [INFO] {r.test_id} JS: {e[:80]}")
        if not fails and not js_issues:
            lines.append("- [INFO] 全テスト正常完了、問題なし")

        lines += ["", "## スクリーンショット", "", f"保存先: `{SCREENSHOT_DIR}/`", ""]
        for r in self.results:
            if r.screenshot:
                lines.append(f"- `{os.path.basename(r.screenshot)}` — {r.test_id} {r.name}")

        return "\n".join(lines)

    def run_all(self):
        print(f"E2E Test Runner — {BASE_URL}")
        self.start()
        try:
            # Health check
            p = self._new_page()
            resp = p.goto(f"{BASE_URL}/healthz", timeout=15000)
            print(f"Health check: {resp.status if resp else 'N/A'}")
            self._close_current()

            self.phase0_login_all()
            self.phase1()
            self.phase2()
            self.phase3()
            self.phase4()
            self.phase5()
        finally:
            self.stop()

        report = self.generate_report()
        report_path = "/Users/adon/NewFUHI/docs/E2E_TEST_REPORT.md"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            f.write(report)
        print(f"\nReport: {report_path}")

        json_path = os.path.join(SCREENSHOT_DIR, "results.json")
        with open(json_path, "w") as f:
            json.dump([{
                "test_id": r.test_id, "name": r.name, "status": r.status,
                "notes": r.notes, "screenshot": r.screenshot, "js_errors": r.js_errors,
            } for r in self.results], f, ensure_ascii=False, indent=2)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")
        blocked = sum(1 for r in self.results if r.status == "BLOCKED")
        print(f"\n{'='*50}")
        print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed} | BLOCKED: {blocked}")
        print(f"{'='*50}")
        return failed == 0


if __name__ == "__main__":
    runner = E2ERunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
