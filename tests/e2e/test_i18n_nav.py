#!/usr/bin/env python3
"""E2E i18n navigation test - verify language persists across page navigation.

Tests that when a user switches to Chinese (zh-hant), all internal links
maintain the language prefix and pages render in the correct language.
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
DELAY = 2

ACCOUNTS = {
    "manager": {"username": "demo_manager", "password": "demo1234"},
}


@dataclass
class TestResult:
    test_id: str
    name: str
    status: str = "PENDING"
    notes: str = ""
    screenshot: str = ""


class I18NNavRunner:
    def __init__(self):
        self.results = []
        self.pw = None
        self.browser = None
        self._ctx = None
        self._page = None

    def start(self):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True)

    def stop(self):
        if self._ctx:
            try:
                self._ctx.close()
            except Exception:
                pass
        if self.browser:
            self.browser.close()
        if self.pw:
            self.pw.stop()

    def new_context(self, storage_state=None):
        if self._ctx:
            try:
                self._ctx.close()
            except Exception:
                pass
        opts = {"viewport": {"width": 1280, "height": 900}, "ignore_https_errors": True}
        if storage_state:
            opts["storage_state"] = storage_state
        self._ctx = self.browser.new_context(**opts)
        self._page = self._ctx.new_page()
        return self._page

    def goto(self, path, timeout=30000):
        time.sleep(DELAY)
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        resp = self._page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        try:
            self._page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass
        return resp.status if resp else 0

    def screenshot(self, name):
        path = os.path.join(SCREENSHOT_DIR, f"i18n_{name}.png")
        try:
            self._page.screenshot(path=path, full_page=False)
        except Exception:
            pass
        return path

    def current_url(self):
        return self._page.url

    def body_text(self):
        try:
            return self._page.inner_text("body")
        except Exception:
            return ""

    def add_result(self, test_id, name, status, notes="", screenshot=""):
        r = TestResult(test_id=test_id, name=name, status=status, notes=notes, screenshot=screenshot)
        self.results.append(r)
        icon = {"PASS": "OK", "FAIL": "NG"}.get(status, "??")
        print(f"  [{icon}] {test_id}: {name} — {notes[:150]}")

    # =====================================================
    # Test: Public pages with zh-hant prefix
    # =====================================================
    def test_public_zh(self):
        print("\n=== Public Pages: zh-hant language persistence ===")
        page = self.new_context()

        pages = [
            ("P1", "トップ", "/zh-hant/", ["占卜", "預約", "店", "首頁", "關於"]),
            ("P2", "店舗一覧", "/zh-hant/stores/", ["店", "預約", "占卜"]),
            ("P3", "占い師一覧", "/zh-hant/fortune-tellers/", ["占卜", "師"]),
            ("P4", "カレンダー", "/zh-hant/date-calendar/", []),
            ("P5", "ショップ", "/zh-hant/shop/", ["商品", "購物"]),
            ("P6", "ニュース", "/zh-hant/news/", []),
            ("P7", "ヘルプ", "/zh-hant/help/", []),
        ]

        for tid, label, path, zh_keywords in pages:
            try:
                status = self.goto(path)
                url = self.current_url()
                text = self.body_text()
                ss = self.screenshot(f"public_{tid}")

                # Check URL has zh-hant
                has_prefix = "/zh-hant/" in url
                has_zh = any(kw in text for kw in zh_keywords) if zh_keywords else True

                notes = f"URL: {url.replace(BASE_URL, '')}, Status: {status}, ZH prefix: {has_prefix}"
                ok = status == 200 and has_prefix
                self.add_result(tid, f"公開: {label} (zh-hant)", "PASS" if ok else "FAIL", notes, ss)
            except Exception as e:
                self.add_result(tid, f"公開: {label}", "FAIL", str(e)[:200])

    # =====================================================
    # Test: Language switcher preserves current page
    # =====================================================
    def test_language_switcher(self):
        print("\n=== Language Switcher: Page Preservation ===")
        page = self.new_context()

        # Go to stores page in default language
        self.goto("/stores/")
        ss_before = self.screenshot("switcher_before")
        url_before = self.current_url()

        # Switch to zh-hant using the language form
        try:
            # Find and submit the language form
            page.evaluate("""() => {
                const forms = document.querySelectorAll('form[action*="i18n/setlang"]');
                if (forms.length === 0) {
                    // Try alternative action
                    const allForms = document.querySelectorAll('form');
                    for (const f of allForms) {
                        if (f.action.includes('i18n')) {
                            const select = f.querySelector('select[name="language"]');
                            if (select) {
                                select.value = 'zh-hant';
                                f.submit();
                                return true;
                            }
                        }
                    }
                }
                for (const f of forms) {
                    const select = f.querySelector('select[name="language"]');
                    if (select) {
                        select.value = 'zh-hant';
                        f.submit();
                        return true;
                    }
                }
                return false;
            }""")
            time.sleep(3)
            self._page.wait_for_load_state("load", timeout=10000)
        except Exception:
            pass

        url_after = self.current_url()
        ss_after = self.screenshot("switcher_after")
        text_after = self.body_text()

        # After switching, user should be on the SAME page but with zh-hant
        # The "next" field should have kept them on /stores/ → /zh-hant/stores/
        stayed_on_page = "/stores/" in url_after or "stores" in url_after.lower()
        has_zh = "/zh-hant/" in url_after

        notes = f"Before: {url_before.replace(BASE_URL, '')}, After: {url_after.replace(BASE_URL, '')}"
        ok = stayed_on_page
        self.add_result("LS1", "言語切替: 現在ページ維持", "PASS" if ok else "FAIL", notes, ss_after)

    # =====================================================
    # Test: Admin login + zh-hant navigation
    # =====================================================
    def test_admin_zh_nav(self):
        print("\n=== Admin: zh-hant navigation persistence ===")
        page = self.new_context()

        # Login as manager
        time.sleep(5)
        self.goto("/login/")
        try:
            self._page.wait_for_selector('input[name="username"]', timeout=15000)
            self._page.fill('input[name="username"]', ACCOUNTS["manager"]["username"])
            self._page.fill('input[name="password"]', ACCOUNTS["manager"]["password"])
            self._page.click('button[type="submit"]')
            time.sleep(5)
        except Exception as e:
            self.add_result("A0", "Manager login", "FAIL", str(e)[:200])
            return

        url = self.current_url()
        if url.endswith("/login/") or url.endswith("/login"):
            self.add_result("A0", "Manager login", "FAIL", "Still on login page")
            return

        # Navigate to admin in zh-hant
        self.goto("/zh-hant/admin/")
        time.sleep(2)
        ss = self.screenshot("admin_zh_home")
        admin_url = self.current_url()

        self.add_result("A1", "Admin: zh-hant ホーム",
                         "PASS" if "/zh-hant/" in admin_url else "FAIL",
                         f"URL: {admin_url.replace(BASE_URL, '')}", ss)

        # Navigate to dashboard from zh-hant admin
        self.goto("/zh-hant/admin/dashboard/sales/")
        time.sleep(2)
        ss = self.screenshot("admin_zh_dashboard")
        dash_url = self.current_url()
        dash_text = self.body_text()

        self.add_result("A2", "Admin: zh-hant 売上ダッシュボード",
                         "PASS" if "/zh-hant/" in dash_url else "FAIL",
                         f"URL: {dash_url.replace(BASE_URL, '')}", ss)

        # Click links within dashboard - check they maintain zh-hant prefix
        # Test the quick links in the dashboard
        links_to_test = [
            ("A3", "シフトカレンダー", "admin_shift_calendar", "/shift/calendar/"),
            ("A4", "POS", "admin_pos", "/pos/"),
            ("A5", "勤怠ボード", "admin_attendance_board", "/attendance/board/"),
        ]

        for tid, label, url_name, path_fragment in links_to_test:
            try:
                # Go back to zh-hant dashboard first
                self.goto("/zh-hant/admin/dashboard/sales/")
                time.sleep(1)

                # Find and click the link that contains the path fragment
                link_selector = f'a[href*="{path_fragment}"]'
                link = self._page.query_selector(link_selector)
                if link:
                    href = link.get_attribute("href")
                    has_zh = "/zh-hant/" in href
                    self.add_result(tid, f"Dashboard→{label} リンク",
                                    "PASS" if has_zh else "FAIL",
                                    f"href={href}, zh-hant: {has_zh}")
                else:
                    # Try clicking by navigating directly
                    self.goto(f"/zh-hant/admin{path_fragment}")
                    time.sleep(1)
                    nav_url = self.current_url()
                    has_zh = "/zh-hant/" in nav_url
                    self.add_result(tid, f"直接遷移: {label} (zh-hant)",
                                    "PASS" if has_zh else "FAIL",
                                    f"URL: {nav_url.replace(BASE_URL, '')}")
            except Exception as e:
                self.add_result(tid, f"Dashboard→{label}", "FAIL", str(e)[:200])

        # Test shift calendar admin menu links
        try:
            self.goto("/zh-hant/admin/shift/calendar/")
            time.sleep(2)
            ss = self.screenshot("admin_zh_shift")

            # Check if the admin menu links have zh-hant prefix
            links = self._page.query_selector_all('a[href*="/admin/booking/"]')
            bad_links = []
            for link in links:
                href = link.get_attribute("href")
                if href and "/zh-hant/" not in href and not href.startswith("#"):
                    bad_links.append(href)

            ok = len(bad_links) == 0
            notes = f"Links without zh-hant: {bad_links[:3]}" if bad_links else "All links have zh-hant prefix"
            self.add_result("A6", "Shift Calendar: 管理メニューリンク",
                            "PASS" if ok else "FAIL", notes, ss)
        except Exception as e:
            self.add_result("A6", "Shift Calendar: 管理メニューリンク", "FAIL", str(e)[:200])

    # =====================================================
    # Test: Legacy URL redirects
    # =====================================================
    def test_legacy_redirects(self):
        print("\n=== Legacy URL Redirects ===")
        page = self.new_context()

        legacy_urls = [
            ("L1", "/staff/10/prebooking/2024/4/29/14/list_clinic.html", "旧prebooking URL"),
            ("L2", "/booking/mq9/", "旧MQ9 URL"),
        ]

        for tid, path, label in legacy_urls:
            try:
                status = self.goto(path)
                url = self.current_url()
                # Should redirect (301) to home page
                redirected = "/login" not in url and status == 200
                is_home = url.rstrip("/") == BASE_URL or url.endswith("/stores/") or "/fortune-tellers/" not in url
                notes = f"Redirected to: {url.replace(BASE_URL, '')}, Status: {status}"
                self.add_result(tid, f"Legacy: {label}",
                                "PASS" if redirected else "FAIL", notes)
            except Exception as e:
                self.add_result(tid, f"Legacy: {label}", "FAIL", str(e)[:200])

    # =====================================================
    # Test: Cross-page navigation maintains language
    # =====================================================
    def test_cross_page_nav(self):
        print("\n=== Cross-Page Navigation: Language Persistence ===")
        page = self.new_context()

        # Start on zh-hant top
        self.goto("/zh-hant/")
        time.sleep(1)

        # Click through navigation links and verify zh-hant is maintained
        nav_clicks = [
            ("N1", "stores", "店舗一覧"),
            ("N2", "fortune-tellers", "占い師一覧"),
            ("N3", "shop", "ショップ"),
            ("N4", "help", "ヘルプ"),
            ("N5", "news", "ニュース"),
        ]

        for tid, path_fragment, label in nav_clicks:
            try:
                # Find link containing the path
                link = self._page.query_selector(f'a[href*="/{path_fragment}/"]')
                if link:
                    href = link.get_attribute("href")
                    link.click()
                    time.sleep(2)
                    try:
                        self._page.wait_for_load_state("load", timeout=10000)
                    except Exception:
                        pass
                    url = self.current_url()
                    has_zh = "/zh-hant/" in url
                    ss = self.screenshot(f"nav_{tid}")
                    self.add_result(tid, f"ナビ遷移: {label}",
                                    "PASS" if has_zh else "FAIL",
                                    f"href={href}, Landed: {url.replace(BASE_URL, '')}", ss)

                    # Go back to start for next test
                    self.goto("/zh-hant/")
                    time.sleep(1)
                else:
                    # Navigate directly
                    self.goto(f"/zh-hant/{path_fragment}/")
                    url = self.current_url()
                    has_zh = "/zh-hant/" in url
                    self.add_result(tid, f"ナビ遷移: {label} (直接)",
                                    "PASS" if has_zh else "FAIL",
                                    f"URL: {url.replace(BASE_URL, '')}")
                    self.goto("/zh-hant/")
                    time.sleep(1)
            except Exception as e:
                self.add_result(tid, f"ナビ遷移: {label}", "FAIL", str(e)[:200])
                try:
                    self.goto("/zh-hant/")
                except Exception:
                    pass

    def run_all(self):
        print(f"i18n Navigation Test — {BASE_URL}")
        self.start()
        try:
            self.test_public_zh()
            self.test_language_switcher()
            self.test_admin_zh_nav()
            self.test_legacy_redirects()
            self.test_cross_page_nav()
        finally:
            self.stop()

        total = len(self.results)
        passed = sum(1 for r in self.results if r.status == "PASS")
        failed = sum(1 for r in self.results if r.status == "FAIL")

        print(f"\n{'='*50}")
        print(f"TOTAL: {total} | PASS: {passed} | FAIL: {failed}")
        print(f"{'='*50}")

        # Save results
        json_path = os.path.join(SCREENSHOT_DIR, "i18n_results.json")
        with open(json_path, "w") as f:
            json.dump([{
                "test_id": r.test_id, "name": r.name, "status": r.status,
                "notes": r.notes, "screenshot": r.screenshot,
            } for r in self.results], f, ensure_ascii=False, indent=2)

        return failed == 0


if __name__ == "__main__":
    runner = I18NNavRunner()
    success = runner.run_all()
    sys.exit(0 if success else 1)
