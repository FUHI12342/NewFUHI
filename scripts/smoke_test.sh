#!/usr/bin/env bash
# ============================================================
# Post-deploy smoke test for timebaibai.com
#
# Usage:
#   ./scripts/smoke_test.sh              # Test production
#   ./scripts/smoke_test.sh http://localhost:8000  # Test local
#
# Exit code: 0 = all pass, 1 = failures found
# ============================================================
set -euo pipefail

BASE_URL="${1:-https://timebaibai.com}"
PASS=0
FAIL=0
WARN=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

check_status() {
    local url="$1"
    local expected="$2"
    local label="$3"

    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "000")

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

    body=$(curl -s --max-time 10 "$url" 2>/dev/null || echo "{}")
    value=$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get(sys.argv[1],''))" "$field" 2>/dev/null || echo "")

    if [ "$value" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC}  $label  ($field=$value)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  $label  (expected $field=$expected, got '$value')"
        FAIL=$((FAIL + 1))
    fi
}

check_health_detail() {
    local url="${BASE_URL}/healthz?detail=1"
    local label="Health detail checks"

    body=$(curl -s --max-time 10 "$url" 2>/dev/null || echo "{}")
    status=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(sys.argv[1],''))" "status" 2>/dev/null || echo "")
    db=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('checks',{}).get(sys.argv[1],''))" "database" 2>/dev/null || echo "")
    celery=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('checks',{}).get(sys.argv[1],''))" "celery" 2>/dev/null || echo "")
    redis=$(echo "$body" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('checks',{}).get(sys.argv[1],''))" "redis" 2>/dev/null || echo "")

    # DB is critical
    if [ "$db" = "ok" ]; then
        echo -e "  ${GREEN}PASS${NC}  Database connectivity  (ok)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${RED}FAIL${NC}  Database connectivity  ($db)"
        FAIL=$((FAIL + 1))
    fi

    # Celery is warning level
    if [ "$celery" = "ok" ]; then
        echo -e "  ${GREEN}PASS${NC}  Celery broker  (ok)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${YELLOW}WARN${NC}  Celery broker  ($celery)"
        WARN=$((WARN + 1))
    fi

    # Redis is warning level
    if [ "$redis" = "ok" ]; then
        echo -e "  ${GREEN}PASS${NC}  Redis  (ok)"
        PASS=$((PASS + 1))
    else
        echo -e "  ${YELLOW}WARN${NC}  Redis  ($redis)"
        WARN=$((WARN + 1))
    fi
}

echo "=========================================="
echo " Smoke Test: ${BASE_URL}"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

# --- 1. Health Check ---
echo "[ Health Check ]"
check_status "${BASE_URL}/healthz" "200" "GET /healthz"
check_json "${BASE_URL}/healthz" "status" "ok" "Health status=ok"
# Detail check requires staff auth - verify it returns 403 for anonymous
check_status "${BASE_URL}/healthz?detail=1" "403" "Detail requires auth"
echo ""

# --- 2. Public Pages (no auth needed) ---
echo "[ Public Pages ]"
check_status "${BASE_URL}/admin/login/" "200" "Admin login page"
echo ""

# --- 3. Auth-protected Admin Pages (expect 302 redirect) ---
echo "[ Admin Pages (auth check → 302) ]"
check_status "${BASE_URL}/admin/" "302" "Admin index"
check_status "${BASE_URL}/admin/shift/calendar/" "302" "Shift calendar"
check_status "${BASE_URL}/admin/shift/today/" "302" "Today shift"
check_status "${BASE_URL}/admin/pos/" "302" "POS"
check_status "${BASE_URL}/admin/analytics/visitors/" "302" "Visitor analytics"
check_status "${BASE_URL}/admin/dashboard/sales/" "302" "Sales dashboard"
check_status "${BASE_URL}/admin/attendance/board/" "302" "Attendance board"
check_status "${BASE_URL}/admin/attendance/performance/" "302" "Staff performance"
check_status "${BASE_URL}/admin/inventory/" "302" "Inventory dashboard"
check_status "${BASE_URL}/admin/ec/orders/" "302" "EC orders"
echo ""

# --- 4. Health Status ---
echo "[ Health Status ]"
check_json "${BASE_URL}/healthz" "status" "ok" "Health endpoint returns ok"
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
