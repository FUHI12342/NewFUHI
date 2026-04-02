#!/usr/bin/env bash
# ============================================================
# Post-deploy smoke test for timebaibai.com
#
# Usage:
#   ./scripts/smoke_test.sh                           # Test production
#   ./scripts/smoke_test.sh http://localhost:8000      # Test local
#   MAINTENANCE=1 ./scripts/smoke_test.sh              # Maintenance-aware
#
# Environment variables:
#   MAINTENANCE=1        - メンテナンスモード中のテスト（匿名503を期待）
#   SMOKE_ADMIN_USER     - 管理者ユーザー名（デフォルト: admin）
#   SMOKE_ADMIN_PASS     - 管理者パスワード（設定時のみ認証テスト実行）
#
# Exit code: 0 = all pass, 1 = failures found
# ============================================================
set -uo pipefail

BASE_URL="${1:-https://timebaibai.com}"
MAINTENANCE="${MAINTENANCE:-0}"
COOKIE_JAR="/tmp/smoke_test_cookies_$$.txt"
PASS=0
FAIL=0
WARN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

cleanup() {
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

check_status() {
    local url="$1"
    local expected="$2"
    local label="$3"
    local auth="${4:-no}"
    local extra=""

    [ "$auth" = "auth" ] && extra="-b $COOKIE_JAR"

    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 $extra "$url" 2>/dev/null || echo "000")

    if [ "$status" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC}  $label  (${status})"
        PASS=$((PASS + 1))
    elif [ "$status" = "000" ]; then
        echo -e "  ${RED}FAIL${NC}  $label  (timeout/connection error)"
        FAIL=$((FAIL + 1))
    else
        echo -e "  ${RED}FAIL${NC}  $label  (expected ${expected}, got ${status})"
        FAIL=$((FAIL + 1))
    fi
}

check_json() {
    local url="$1"
    local field="$2"
    local expected="$3"
    local label="$4"

    local body
    body=$(curl -s --max-time 10 "$url" 2>/dev/null || echo "{}")
    local value
    value=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get(sys.argv[1],''))" "$field" 2>/dev/null || echo "")

    if [ "$value" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC}  $label  ($field=$value)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  $label  (expected $field=$expected, got '$value')"
        FAIL=$((FAIL + 1))
    fi
}

admin_login() {
    local user="${SMOKE_ADMIN_USER:-admin}"
    local pass="${SMOKE_ADMIN_PASS:-}"

    if [ -z "$pass" ]; then
        echo -e "  ${YELLOW}SKIP${NC}  管理者ログイン (SMOKE_ADMIN_PASS 未設定)"
        WARN=$((WARN + 1))
        return 1
    fi

    # CSRFトークン取得
    local csrf
    csrf=$(curl -s -c "$COOKIE_JAR" --max-time 10 "${BASE_URL}/admin/login/" 2>/dev/null | \
        grep -o 'csrfmiddlewaretoken" value="[^"]*"' | \
        head -1 | sed 's/csrfmiddlewaretoken" value="//;s/"$//')

    if [ -z "$csrf" ]; then
        echo -e "  ${RED}FAIL${NC}  管理者ログイン (CSRFトークン取得不可)"
        FAIL=$((FAIL + 1))
        return 1
    fi

    # ログイン
    local code
    code=$(curl -s -o /dev/null -w '%{http_code}' \
        -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
        -d "csrfmiddlewaretoken=${csrf}&username=${user}&password=${pass}&next=/admin/" \
        -H "Referer: ${BASE_URL}/admin/login/" \
        -L --max-time 10 \
        "${BASE_URL}/admin/login/" 2>/dev/null || echo "000")

    if [ "$code" = "200" ] || [ "$code" = "302" ]; then
        echo -e "  ${GREEN}PASS${NC}  管理者ログイン (HTTP $code)"
        PASS=$((PASS + 1))
        return 0
    else
        echo -e "  ${RED}FAIL${NC}  管理者ログイン (HTTP $code)"
        FAIL=$((FAIL + 1))
        return 1
    fi
}

echo "=========================================="
echo " Smoke Test: ${BASE_URL}"
if [ "$MAINTENANCE" = "1" ]; then
    echo " Mode: メンテナンス中（匿名503を期待）"
fi
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# --- 1. Health Check (メンテバイパス対象) ---
echo "[ Health Check ]"
check_status "${BASE_URL}/healthz" "200" "GET /healthz"
check_json "${BASE_URL}/healthz" "status" "ok" "Health status=ok"
echo ""

# --- 2. メンテナンスモード確認 ---
if [ "$MAINTENANCE" = "1" ]; then
    echo "[ メンテナンスモード確認 ]"
    check_status "${BASE_URL}/" "503" "匿名ユーザー → 503"
    check_status "${BASE_URL}/admin/login/" "200" "管理者ログイン画面 → 200（バイパス）"
    echo ""
fi

# --- 3. 管理者ログイン＆認証付きテスト ---
echo "[ 管理者認証テスト ]"
if admin_login; then
    LOGGED_IN=1
else
    LOGGED_IN=0
fi
echo ""

if [ "$LOGGED_IN" = "1" ]; then
    echo "[ 管理画面ページ（認証済み） ]"
    check_status "${BASE_URL}/admin/" "200" "管理画面トップ" "auth"
    check_status "${BASE_URL}/admin/dashboard/sales/" "200" "売上ダッシュボード" "auth"
    check_status "${BASE_URL}/admin/shift/calendar/" "200" "シフトカレンダー" "auth"
    check_status "${BASE_URL}/admin/pos/" "200" "POS" "auth"
    check_status "${BASE_URL}/admin/inventory/" "200" "在庫管理" "auth"
    echo ""

    echo "[ 公開ページ（認証済み＝メンテバイパス） ]"
    check_status "${BASE_URL}/ja/booking/" "200" "予約トップ" "auth"
    echo ""
fi

# --- 4. 管理画面（未認証 → リダイレクト or 503） ---
if [ "$MAINTENANCE" = "0" ]; then
    echo "[ 管理画面（未認証 → 302リダイレクト） ]"
    check_status "${BASE_URL}/admin/" "302" "管理画面トップ"
    check_status "${BASE_URL}/admin/shift/calendar/" "302" "シフトカレンダー"
    check_status "${BASE_URL}/admin/pos/" "302" "POS"
    check_status "${BASE_URL}/admin/dashboard/sales/" "302" "売上ダッシュボード"
    echo ""
fi

# --- 5. 静的ファイル ---
echo "[ 静的ファイル ]"
check_status "${BASE_URL}/static/css/style.css" "200" "CSS (style.css)"
check_status "${BASE_URL}/static/js/admin_darkmode.js" "200" "JS (admin_darkmode.js)"
echo ""

# --- Summary ---
echo "=========================================="
TOTAL=$((PASS + FAIL + WARN))
echo -e " Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}, ${YELLOW}${WARN} warnings${NC} / ${TOTAL} total"
echo "=========================================="

if [ "$FAIL" -gt 0 ]; then
    echo -e " ${RED}SMOKE TEST FAILED${NC}"
    exit 1
else
    echo -e " ${GREEN}SMOKE TEST PASSED${NC}"
    exit 0
fi
